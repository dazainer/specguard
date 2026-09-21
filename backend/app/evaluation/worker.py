"""Single durable SQLite worker supervising one bounded evaluator subprocess."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from app.config import get_settings
from app.evaluation.execution_runner import DockerRunner, local_endpoint
from app.evaluation.public_data import scrub
from app.evaluation.store import Store, TERMINAL
from app.evaluation.job_lock import job_lock
from app.schemas.evaluation import EvaluationReport


def cleanup_containers(run_id, image):
    # Exact durable run label; never remove another run's or an arbitrary container.
    runner=DockerRunner(image)
    with tempfile.TemporaryDirectory(prefix='specguard-cleanup-') as config:
        client=['docker','--config',config,'--host',local_endpoint()]
        ids=runner._control(client,'container','ls','--all','--filter',f'label=io.specguard.evaluation.run={run_id}','--format','{{.ID}}').decode().split()
        for identifier in ids:
            runner._control(client,'rm','--force',identifier)


def index_result(store, settings, run, owner, override=None):
    output=settings.evaluation_artifacts.resolve()/run['id']
    report=None
    timings={}
    try:
        report=EvaluationReport.model_validate_json((output/'report.json').read_bytes())
        if report.status not in TERMINAL:
            override=override or 'worker_interrupted'
        if override:
            report=report.model_copy(update={'status':'cancelled' if override=='cancelled' else 'failed','failure_reason':override})
        report=EvaluationReport.model_validate(report.model_dump())
        if (output/'timings.json').exists():
            timings=json.loads((output/'timings.json').read_text())
        with store.connection(write=True) as connection:
            for artifact in report.artifacts:
                connection.execute('INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?)',
                    (run['id'],artifact.path,artifact.sha256,artifact.size_bytes,int(report.generated.accepted_tests is not None and report.generated.rejected_tests==0)))
            for suite in ('native','generated'):
                path=output/f'{suite}-mutants.jsonl'
                if not path.exists():
                    continue
                with path.open() as records:
                    for line in records:
                        try:
                            value=json.loads(line)
                        except ValueError:
                            # A killed writer may leave one partial final record.
                            if report.status != 'completed':
                                break
                            raise
                        connection.execute('INSERT OR REPLACE INTO mutants VALUES (?,?,?,?,?)',
                            (run['id'],suite,value['id'],value['status'],json.dumps(scrub(value,settings.openai_api_key))))
        public=scrub(report.model_dump(),settings.openai_api_key)
        if not store.finish(run['id'],owner,report.status,report.failure_reason,public,timings):
            return
        # finish resolves late cancellation atomically with the terminal write.
        public=json.loads(store.get_run(run['id'])['report_json'])
        temporary=output/'report.tmp'
        temporary.write_text(json.dumps(public,indent=2))
        temporary.replace(output/'report.json')
        from app.evaluation.reporting import write_run_summary
        write_run_summary(EvaluationReport.model_validate(public),output)
    except (ValueError, OSError, KeyError):
        store.finish(run['id'],owner,'cancelled' if override=='cancelled' else 'failed',override or 'result_unavailable')


def prune(store, settings, *, now=None):
    now=time.time() if now is None else now
    root=settings.evaluation_artifacts.resolve()
    rows=store.rows("SELECT * FROM runs WHERE status IN ('completed','failed','cancelled') AND pruned=0 ORDER BY finished_at")
    sizes={row['id']:sum(path.stat().st_size for path in (root/row['id']).rglob('*') if path.is_file() and not path.is_symlink()) for row in rows}
    total=sum(sizes.values())
    for row in rows:
        if row['finished_at'] > now-settings.evaluation_retention_days*86400 and total <= settings.evaluation_storage_mb*1024*1024:
            continue
        path=root/row['id']
        if path.is_symlink():
            raise ValueError('Refusing symlink artifact root')
        shutil.rmtree(path,ignore_errors=False) if path.exists() else None
        total-=sizes[row['id']]
        with store.connection(write=True) as connection:
            # Keep reports and metrics; remove bulky detailed observations.
            connection.execute('DELETE FROM mutants WHERE run_id=?',(row['id'],))
            connection.execute('UPDATE runs SET pruned=1 WHERE id=?',(row['id'],))


class Worker:
    def __init__(self, settings=None):
        self.settings=settings or get_settings()
        self.store=Store(self.settings.evaluation_db)
        self.owner=str(uuid.uuid4())
        self.stopping=False

    def recover(self):
        rows=self.store.rows("SELECT * FROM runs WHERE status NOT IN ('queued','completed','failed','cancelled') AND owner!=?",(self.owner,))
        for row in rows:
            # The prior child sees the new lease and stops before releasing this
            # lock. Only then may recovery remove containers or publish results.
            with job_lock(self.store,row['id']):
                try:
                    cleanup_containers(row['id'],row['image'])
                    reason='worker_lost'
                except Exception:
                    reason='worker_lost_cleanup_unconfirmed'
                index_result(self.store,self.settings,row,row['owner'],reason)
            self.store.heartbeat(self.owner)

    def execute(self, run):
        root=self.settings.evaluation_artifacts.resolve()
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        # No unbounded supervisor stdout logs: child emits only structured events
        # already persisted in SQLite; all test output goes through DockerRunner.
        env=dict(os.environ,EVALUATION_DB=str(self.store.path),EVALUATION_ARTIFACTS=str(root),
                 EVALUATION_SUBJECTS=str(self.settings.evaluation_subjects.resolve()))
        try:
            process=subprocess.Popen([sys.executable,'-m','app.evaluation.job_process',run['id'],self.owner],
                env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        except OSError:
            self.store.finish(run['id'],self.owner,'failed','worker_spawn_failed')
            return
        reason=None
        signalled_at=None
        last_stage=None
        try:
            while process.poll() is None:
                self.store.heartbeat(self.owner)
                current=self.store.get_run(run['id'])
                if current['status'] != last_stage:
                    last_stage=current['status']
                    print(json.dumps(dict(run_id=run['id'],stage=last_stage)),flush=True)
                if current['cancel_requested']:
                    reason='cancelled'
                elif self.stopping:
                    reason=reason or 'worker_stopped'
                elif time.time() > run['started_at']+run['max_seconds']:
                    reason=reason or 'run_deadline'
                used=sum(path.stat().st_size for path in (root/run['id']).rglob('*') if path.is_file() and not path.is_symlink())
                if used > self.settings.evaluation_run_storage_mb*1024*1024:
                    reason=reason or 'artifact_limit'
                if reason and signalled_at is None:
                    process.send_signal(signal.SIGINT)
                    signalled_at=time.monotonic()
                if signalled_at and time.monotonic()-signalled_at > 15:
                    os.killpg(process.pid,signal.SIGKILL)
                    break
                time.sleep(0.5)
        except Exception:
            reason=reason or 'worker_supervisor_failed'
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=10)
            try:
                cleanup_containers(run['id'],run['image'])
            except Exception:
                reason='cleanup_unconfirmed'
            index_result(self.store,self.settings,run,self.owner,reason)
        result=self.store.get_run(run['id'])
        print(json.dumps(dict(run_id=run['id'],stage=result['status'],failure_reason=result['failure_reason'])),flush=True)

    def run(self, once=False):
        # Local single-host deployment: an OS lock prevents a paused supervisor
        # from overlapping a replacement merely because its heartbeat expired.
        with self.store.path.with_suffix('.worker.lock').open('a') as lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                from app.evaluation.store import Conflict
                raise Conflict('Another evaluation worker holds the process lock')
            self._run(once)

    def _run(self, once):
        self.store.lease_worker(self.owner)
        try:
            self.recover()
            while not self.stopping:
                self.store.heartbeat(self.owner)
                run=self.store.claim(self.owner)
                if run:
                    self.execute(run)
                prune(self.store,self.settings)
                if once:
                    break
                time.sleep(1)
        finally:
            self.store.release(self.owner)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--prune',action='store_true')
    parser.add_argument('--health',action='store_true')
    args=parser.parse_args()
    worker=Worker()
    if args.health:
        raise SystemExit(0 if all(worker.store.ready().values()) else 1)
    if args.prune:
        prune(worker.store,worker.settings)
        return
    def stop(*_):
        worker.stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    worker.run(once=args.once)


if __name__=='__main__':
    main()
