import json
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.evaluation.manifest import load_manifest
from app.evaluation.store import Store, Conflict
from app.evaluation.worker import Worker, prune
from app.evaluation.public_data import scrub
from app.routes import evaluations

IMAGE='sha256:'+'a'*64


@pytest.fixture
def product(tmp_path, subject, monkeypatch):
    settings=Settings(evaluation_db=tmp_path/'evaluations.db',evaluation_artifacts=tmp_path/'runs',
                      evaluation_subjects=subject.parent,evaluation_runner_image=IMAGE)
    store=Store(settings.evaluation_db)
    store.migrate()
    monkeypatch.setattr(evaluations,'get_settings',lambda:settings)
    return settings,store


def target(store, settings):
    manifest=load_manifest(settings.evaluation_subjects/'access_policy/specguard.yaml')
    return store.add_target('Access policy','access_policy',manifest.model_dump())


def queue(store,settings,key='request-key',max_seconds=900):
    t=target(store,settings)
    return store.enqueue(t['id'],dict(strategy='contract-v1',baseline_only=True),key,settings.evaluation_runner_image,max_seconds)


def test_migration_is_repeatable_and_never_implicit(tmp_path):
    store=Store(tmp_path/'db.sqlite')
    assert store.ready()==dict(database=False,worker=False)
    assert not store.path.exists()
    store.migrate(); store.migrate()
    assert store.ready()['database']
    assert store.rows('SELECT version_num FROM alembic_version')[0]['version_num']=='0001_evaluations'


def test_submission_idempotency_and_conflicts(product):
    settings,store=product
    run=queue(store,settings)
    repeated=store.enqueue(run['target_id'],json.loads(run['options_json']),'request-key',IMAGE)
    assert repeated['id']==run['id']
    with pytest.raises(Conflict):
        store.enqueue(run['target_id'],dict(strategy='boundary-v1',baseline_only=True),'request-key',IMAGE)
    assert len(store.rows('SELECT * FROM runs'))==1


def test_claims_are_exclusive_and_old_owner_is_fenced(product):
    settings,store=product
    run=queue(store,settings)
    store.lease_worker('first')
    with pytest.raises(Conflict): store.lease_worker('second')
    claimed=store.claim('first')
    assert claimed['id']==run['id'] and store.claim('first') is None
    with store.connection(write=True) as connection:
        connection.execute('UPDATE workers SET heartbeat=?',(time.time()-60,))
    store.lease_worker('second')
    with pytest.raises(Conflict): store.heartbeat('first')
    with pytest.raises(Conflict): store.claim('first')


def test_queued_cancellation_is_terminal_and_idempotent(product):
    settings,store=product
    run=queue(store,settings)
    assert store.cancel(run['id'])['status']=='cancelled'
    assert store.cancel(run['id'])['status']=='cancelled'
    store.lease_worker('worker')
    assert store.claim('worker') is None


def test_recovery_preserves_failed_run_record(product,monkeypatch):
    settings,store=product
    run=queue(store,settings)
    store.lease_worker('dead-worker'); store.claim('dead-worker')
    store.release('dead-worker')
    calls=[]
    monkeypatch.setattr('app.evaluation.worker.cleanup_containers',lambda run_id,image:calls.append(run_id))
    worker=Worker(settings); store.lease_worker(worker.owner); worker.recover()
    saved=store.get_run(run['id'])
    assert saved['status']=='failed' and saved['failure_reason']=='worker_lost'
    assert calls==[run['id']]


def test_retention_removes_only_terminal_artifacts_and_keeps_report(product):
    settings,store=product
    complete=queue(store,settings)
    store.lease_worker('worker'); store.claim('worker')
    store.finish(complete['id'],'worker','completed',report={'retained':'summary'})
    queued=queue(store,settings,'other-key')
    for run in (complete,queued):
        root=settings.evaluation_artifacts/run['id']; root.mkdir(parents=True)
        (root/'file.txt').write_text('artifact')
    prune(store,settings,now=time.time()+8*86400)
    assert not (settings.evaluation_artifacts/complete['id']).exists()
    assert (settings.evaluation_artifacts/queued['id']).exists()
    assert json.loads(store.get_run(complete['id'])['report_json'])=={'retained':'summary','status':'completed','failure_reason':None}
    assert store.get_run(complete['id'])['pruned']==1


def test_public_log_scrubbing_and_byte_cap():
    content='password=hidden sk-abcdefghijklmnopqrstuvwxyz Bearer abcdefghijkl private-canary '
    value=scrub({'stdout':content+'x'*20000},'private-canary')
    assert 'hidden' not in value['stdout'] and 'abcdefghijklmnopqrstuvwxyz' not in value['stdout']
    assert 'private-canary' not in value['stdout'] and 'abcdefghijkl' not in value['stdout']
    assert value['stdout'].endswith('[truncated]')


def test_late_cancel_wins_terminal_write_and_report(product):
    settings,store=product
    run=queue(store,settings)
    store.lease_worker('worker'); store.claim('worker'); store.cancel(run['id'])
    store.finish(run['id'],'worker','completed',report={'status':'completed'})
    saved=store.get_run(run['id'])
    assert saved['status']=='cancelled'
    assert json.loads(saved['report_json'])['status']=='cancelled'


def test_supervisor_spawn_failure_finishes_claim(product,monkeypatch):
    settings,store=product
    queue(store,settings)
    worker=Worker(settings); store.lease_worker(worker.owner)
    claimed=store.claim(worker.owner)
    def fail(*args,**kwargs): raise OSError('sensitive internal detail')
    monkeypatch.setattr('app.evaluation.worker.subprocess.Popen',fail)
    worker.execute(claimed)
    assert store.get_run(claimed['id'])['failure_reason']=='worker_spawn_failed'


def test_process_lock_prevents_overlapping_supervisors(product):
    import fcntl
    settings,store=product
    with store.path.with_suffix('.worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Conflict,match='process lock'):
            Worker(settings).run(True)


def test_cleanup_failure_stays_visible_even_after_cancellation(product,monkeypatch):
    settings,store=product
    run=queue(store,settings)
    store.lease_worker('dead'); store.claim('dead'); store.cancel(run['id']); store.release('dead')
    def fail(*args): raise RuntimeError('Docker unavailable')
    monkeypatch.setattr('app.evaluation.worker.cleanup_containers',fail)
    worker=Worker(settings); store.lease_worker(worker.owner); worker.recover()
    saved=store.get_run(run['id'])
    assert saved['status']=='failed'
    assert saved['failure_reason']=='worker_lost_cleanup_unconfirmed'


def test_storage_retention_preserves_active_runs(product):
    settings,store=product
    settings.evaluation_storage_mb=0
    run=queue(store,settings)
    store.lease_worker('worker'); store.claim('worker')
    root=settings.evaluation_artifacts/run['id']; root.mkdir(parents=True)
    (root/'artifact').write_text('x')
    prune(store,settings)
    assert root.exists()
    store.finish(run['id'],'worker','failed','test')
    prune(store,settings)
    assert not root.exists() and store.get_run(run['id'])['pruned']


def test_interrupted_partial_mutant_record_keeps_prior_observations(product,subject):
    from app.evaluation.prepare import prepare
    from app.evaluation.worker import index_result
    settings,store=product
    run=queue(store,settings)
    store.lease_worker('worker'); claimed=store.claim('worker')
    output=settings.evaluation_artifacts/run['id']
    prepare(subject/'specguard.yaml',output,fixture=subject/'generation-fixture.json')
    record={'id':'first','status':'killed'}
    (output/'native-mutants.jsonl').write_text(json.dumps(record)+'\n{"id":')
    index_result(store,settings,claimed,'worker','worker_lost')
    saved=store.get_run(run['id'])
    assert saved['status']=='failed' and saved['failure_reason']=='worker_lost'
    assert json.loads(saved['report_json'])['status']=='failed'
    assert store.rows('SELECT mutant_id FROM mutants')==[{'mutant_id':'first'}]
    assert json.loads((output/'report.json').read_text())['status']=='failed'


async def test_api_catalog_targets_idempotency_restart_and_cancel(product):
    settings,store=product
    app=FastAPI(); app.include_router(evaluations.router)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        assert len((await client.get('/api/evaluations/catalog')).json())==5
        response=await client.post('/api/evaluations/targets',json={'name':'Policy','subject':'access_policy'})
        assert response.status_code==201
        target_id=response.json()['id']
        body=dict(target_id=target_id,idempotency_key='api-retry-key',baseline_only=True)
        first=await client.post('/api/evaluations/runs',json=body)
        second=await client.post('/api/evaluations/runs',json=body)
        assert first.status_code==202 and second.json()['id']==first.json()['id']
        run_id=first.json()['id']
        assert (await client.post('/api/evaluations/runs',json=body|{'strategy':'boundary-v1'})).status_code==409
        assert (await client.post('/api/evaluations/targets',json={'name':'Bad','subject':'../../etc'})).status_code==422
        assert (await client.post('/api/evaluations/runs',json=body|{'live':True})).status_code==422
    restarted=FastAPI(); restarted.include_router(evaluations.router)
    async with AsyncClient(transport=ASGITransport(app=restarted),base_url='http://test') as client:
        assert (await client.get(f'/api/evaluations/runs/{run_id}')).json()['status']=='queued'
        assert (await client.post(f'/api/evaluations/runs/{run_id}/cancel')).json()['status']=='cancelled'
        assert (await client.get(f'/api/evaluations/runs/{run_id}/artifact',params={'path':'../.env'})).status_code==404
        assert (await client.get('/api/evaluations/metrics')).json()['states'][0]['count']==1
        assert (await client.get('/api/evaluations/ready')).status_code==503
