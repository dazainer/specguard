"""SQLite durable queue. Schema changes are applied only through Alembic."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from app.evaluation.context_builder import canonical_json, sha256

TERMINAL = {'completed', 'failed', 'cancelled'}
ACTIVE = {'preparing', 'generating', 'collecting', 'baseline_running', 'mutating'}


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def migrate(self):
        from alembic.config import Config
        from alembic import command
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        config = Config(str(Path(__file__).resolve().parents[2] / 'evaluation-alembic.ini'))
        config.attributes['database_path'] = self.path
        command.upgrade(config, 'head')
        with self.connection() as connection:
            connection.execute('PRAGMA journal_mode=WAL')

    @contextmanager
    def connection(self, *, write=False):
        connection = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def rows(self, sql, params=()):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(sql, params)]

    def get_run(self, run_id):
        rows = self.rows('SELECT * FROM runs WHERE id=?', (run_id,))
        return rows[0] if rows else None

    def add_target(self, name, subject, manifest):
        value = canonical_json(manifest).decode()
        target_id = str(uuid.uuid4())
        with self.connection(write=True) as connection:
            connection.execute('INSERT INTO targets VALUES (?,?,?,?,?,?)',
                (target_id, name, subject, value, sha256(value.encode()), time.time()))
        return self.rows('SELECT * FROM targets WHERE id=?', (target_id,))[0]

    def enqueue(self, target_id, options, key, image, max_seconds=900):
        fingerprint = sha256(canonical_json(dict(target=target_id, options=options, image=image, max_seconds=max_seconds)))
        with self.connection(write=True) as connection:
            existing = connection.execute('SELECT * FROM runs WHERE idempotency_key=?', (key,)).fetchone()
            if existing:
                if existing['request_hash'] != fingerprint:
                    raise Conflict('Idempotency key was already used for a different request')
                return dict(existing)
            if not connection.execute('SELECT 1 FROM targets WHERE id=?', (target_id,)).fetchone():
                raise KeyError('target')
            if connection.execute("SELECT count(*) FROM runs WHERE status='queued'").fetchone()[0] >= 100:
                raise Conflict('Queue is full')
            run_id = str(uuid.uuid4())
            now = time.time()
            connection.execute('INSERT INTO runs (id,target_id,idempotency_key,request_hash,options_json,status,created_at,max_seconds,image) VALUES (?,?,?,?,?,?,?,?,?)',
                (run_id, target_id, key, fingerprint, json.dumps(options), 'queued', now, max_seconds, image))
            connection.execute('INSERT INTO events (run_id,stage,at) VALUES (?,?,?)', (run_id,'queued',now))
        return self.get_run(run_id)

    def cancel(self, run_id):
        with self.connection(write=True) as connection:
            run = connection.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if not run:
                raise KeyError('run')
            if run['status'] not in TERMINAL:
                connection.execute('UPDATE runs SET cancel_requested=1 WHERE id=?', (run_id,))
                if run['status'] == 'queued':
                    connection.execute("UPDATE runs SET status='cancelled',finished_at=?,failure_reason='cancelled' WHERE id=?", (time.time(),run_id))
                    connection.execute('INSERT INTO events (run_id,stage,at) VALUES (?,?,?)', (run_id,'cancelled',time.time()))
        return self.get_run(run_id)

    def lease_worker(self, owner, *, now=None):
        now = time.time() if now is None else now
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT * FROM workers WHERE id='main'").fetchone()
            if row and row['owner'] != owner and row['heartbeat'] > now - 30:
                raise Conflict('Another evaluation worker is active')
            connection.execute("INSERT INTO workers VALUES ('main',?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,heartbeat=excluded.heartbeat", (owner,now))

    def heartbeat(self, owner):
        with self.connection(write=True) as connection:
            if connection.execute("UPDATE workers SET heartbeat=? WHERE id='main' AND owner=?", (time.time(),owner)).rowcount != 1:
                raise Conflict('Worker lease lost')
            connection.execute("UPDATE runs SET heartbeat=? WHERE owner=? AND status NOT IN ('completed','failed','cancelled')", (time.time(),owner))

    def release(self, owner):
        with self.connection(write=True) as connection:
            connection.execute('DELETE FROM workers WHERE owner=?', (owner,))

    def claim(self, owner):
        with self.connection(write=True) as connection:
            lease = connection.execute("SELECT * FROM workers WHERE id='main' AND owner=?", (owner,)).fetchone()
            if not lease or lease['heartbeat'] < time.time() - 30:
                raise Conflict('Worker lease expired')
            row = connection.execute("SELECT * FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            now=time.time()
            connection.execute("UPDATE runs SET status='preparing',owner=?,started_at=?,heartbeat=? WHERE id=?", (owner,now,now,row['id']))
            connection.execute('INSERT INTO events (run_id,stage,at) VALUES (?,?,?)', (row['id'],'preparing',now))
            result=dict(row)
            result.update(status='preparing',owner=owner,started_at=now,heartbeat=now)
            return result

    def progress(self, run_id, owner, report):
        with self.connection(write=True) as connection:
            row=connection.execute('SELECT * FROM runs WHERE id=? AND owner=?', (run_id,owner)).fetchone()
            if not row or row['status'] in TERMINAL:
                raise Conflict('Run ownership lost')
            stage=report.status
            # Supervisor owns the terminal transition after indexing artifacts.
            if stage in TERMINAL:
                return
            connection.execute('UPDATE runs SET status=?,report_json=? WHERE id=?', (stage,report.model_dump_json(),run_id))
            if row['status'] != stage:
                connection.execute('INSERT INTO events (run_id,stage,at) VALUES (?,?,?)', (run_id,stage,time.time()))

    def finish(self, run_id, owner, status, reason=None, report=None, timings=None):
        if status not in TERMINAL:
            raise ValueError('Invalid terminal state')
        with self.connection(write=True) as connection:
            row=connection.execute('SELECT * FROM runs WHERE id=? AND owner=?', (run_id,owner)).fetchone()
            if not row or row['status'] in TERMINAL:
                return False
            if row['cancel_requested'] and reason not in {'cleanup_unconfirmed','worker_lost_cleanup_unconfirmed'}:
                status,reason='cancelled','cancelled'
            if report is None and row['report_json']:
                report=json.loads(row['report_json'])
            if report is not None:
                report=dict(report,status=status,failure_reason=reason)
            connection.execute('UPDATE runs SET status=?,finished_at=?,failure_reason=?,report_json=?,timings_json=? WHERE id=?',
                (status,time.time(),reason,json.dumps(report) if report else row['report_json'],json.dumps(timings or {}),run_id))
            connection.execute('INSERT INTO events (run_id,stage,at) VALUES (?,?,?)', (run_id,status,time.time()))
        return True

    def ready(self):
        try:
            versions=self.rows('SELECT version_num FROM alembic_version')
            workers=self.rows("SELECT heartbeat FROM workers WHERE id='main'")
            return dict(database=bool(versions and versions[0]['version_num']=='0001_evaluations'),
                        worker=bool(workers and workers[0]['heartbeat'] > time.time()-30))
        except sqlite3.Error:
            return dict(database=False,worker=False)
