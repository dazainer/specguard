"""One supervised durable job; invokes the same evaluator as the CLI."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time

from app.config import get_settings
from app.evaluation.context_builder import canonical_json, sha256
from app.evaluation.control import EvaluationStopped
from app.evaluation.evaluate import evaluate
from app.evaluation.execution_runner import DockerRunner
from app.evaluation.manifest import load_manifest
from app.evaluation.paths import safe_path
from app.evaluation.store import Store, TERMINAL
from app.evaluation.job_lock import job_lock


async def run_job(run_id, owner):
    settings=get_settings()
    store=Store(settings.evaluation_db)
    run=store.get_run(run_id)
    parent_pid=os.getppid()
    if not run or run['owner'] != owner or run['status'] in TERMINAL:
        raise ValueError('Run ownership lost')
    target=store.rows('SELECT * FROM targets WHERE id=?', (run['target_id'],))[0]
    manifest_path=safe_path(settings.evaluation_subjects.resolve(), target['subject']+'/specguard.yaml',must_exist=True)
    manifest=load_manifest(manifest_path)
    if sha256(canonical_json(manifest.model_dump())) != target['manifest_hash']:
        raise ValueError('Target manifest changed; register a new target')
    def interrupted():
        if os.getppid()!=parent_pid:
            return 'worker_lost'
        current=store.get_run(run_id)
        workers=store.rows("SELECT * FROM workers WHERE id='main'")
        if not current or current['owner'] != owner or current['status'] in TERMINAL:
            return 'worker_lease_lost'
        if not workers or workers[0]['owner'] != owner or workers[0]['heartbeat'] < time.time()-30:
            return 'worker_lease_lost'
        if current['cancel_requested']:
            return 'cancelled'
        if time.time() > run['started_at'] + run['max_seconds']:
            return 'run_deadline'
        return None
    def progress(report):
        reason=interrupted()
        if reason:
            raise EvaluationStopped(reason)
        store.progress(run_id, owner, report)
        print(json.dumps(dict(run_id=run_id,stage=report.status,at=time.time())),flush=True)
    options=json.loads(run['options_json'])
    runner=DockerRunner(run['image'],interrupt_check=interrupted,job_id=run_id)
    def stop_signal(*_):
        raise EvaluationStopped(interrupted() or 'worker_stopped')
    signal.signal(signal.SIGINT,stop_signal)
    signal.signal(signal.SIGTERM,stop_signal)
    return await evaluate(manifest_path,settings.evaluation_artifacts.resolve()/run_id,run['image'],
                          strategy=options['strategy'],mutate=not options['baseline_only'],runner=runner,progress=progress)


if __name__ == '__main__':
    try:
        with job_lock(Store(get_settings().evaluation_db),sys.argv[1]):
            report=asyncio.run(run_job(sys.argv[1],sys.argv[2]))
        raise SystemExit(0 if report.status=='completed' else 1)
    except (Exception, KeyboardInterrupt):
        # No provider/target content in process errors; supervisor records failure.
        print(json.dumps({'event':'job_process_failed'}),flush=True)
        raise SystemExit(1)
