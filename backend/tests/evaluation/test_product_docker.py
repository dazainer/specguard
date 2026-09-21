import asyncio
import json
import os
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.evaluation.worker import Worker
from app.routes import evaluations
from app.schemas.evaluation import EvaluationReport
from tests.evaluation.test_product import product, queue

pytestmark=[pytest.mark.docker,pytest.mark.skipif(os.environ.get('SPECGUARD_DOCKER_TESTS')!='1',reason='opt-in Docker verification')]


async def test_web_run_survives_api_restart_and_exports_cli_contract(product):
    settings,store=product
    settings.evaluation_runner_image=os.environ['SPECGUARD_RUNNER_IMAGE']
    app=FastAPI(); app.include_router(evaluations.router)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        target=(await client.post('/api/evaluations/targets',json={'name':'Policy','subject':'access_policy'})).json()
        response=await client.post('/api/evaluations/runs',json={'target_id':target['id'],'idempotency_key':'restart-evidence','baseline_only':False})
        assert response.status_code==202,response.text
        run_id=response.json()['id']
    worker=Worker(settings)
    running=asyncio.create_task(asyncio.to_thread(worker.run,True))
    # The API lifecycle ends above; an independent application instance sees the
    # same durable record while the separate evaluator child is working.
    restarted=FastAPI(); restarted.include_router(evaluations.router)
    async with AsyncClient(transport=ASGITransport(app=restarted),base_url='http://test') as client:
        seen=set()
        while not running.done():
            current=(await client.get(f'/api/evaluations/runs/{run_id}')).json()
            seen.add(current['status'])
            await asyncio.sleep(.2)
        await running
        saved=(await client.get(f'/api/evaluations/runs/{run_id}')).json()
        assert saved['status']=='completed',saved
        exported=(await client.get(f'/api/evaluations/runs/{run_id}/export')).json()
        report=EvaluationReport.model_validate(exported)
        assert report.native.mutation.inventory_sha256==report.generated.mutation.inventory_sha256
        assert report.model_dump()==json.loads((settings.evaluation_artifacts/run_id/'report.json').read_text())
        assert len((await client.get(f'/api/evaluations/runs/{run_id}/artifacts')).json())>0
        assert (await client.get(f'/api/evaluations/runs/{run_id}/mutants')).json()['total']>0
        assert (await client.get(f'/api/evaluations/runs/{run_id}/logs')).json()
        assert (await client.get(f'/api/evaluations/runs/{run_id}/export?format=csv')).status_code==200
        assert {'preparing','generating','collecting','baseline_running','mutating','completed'} <= {e['stage'] for e in saved['events']}


async def test_active_cancellation_cleans_up_and_persists(product):
    settings,store=product
    settings.evaluation_runner_image=os.environ['SPECGUARD_RUNNER_IMAGE']
    run=queue(store,settings)
    worker=Worker(settings)
    running=asyncio.create_task(asyncio.to_thread(worker.run,True))
    for _ in range(100):
        if store.get_run(run['id'])['status']=='baseline_running':
            break
        await asyncio.sleep(.1)
    store.cancel(run['id'])
    await running
    saved=store.get_run(run['id'])
    assert saved['status']=='cancelled',saved
    assert saved['failure_reason']=='cancelled'


@pytest.mark.parametrize('limit,reason', [('deadline','run_deadline'),('storage','artifact_limit')])
def test_supervisor_enforces_limits(product,limit,reason):
    settings,store=product
    settings.evaluation_runner_image=os.environ['SPECGUARD_RUNNER_IMAGE']
    if limit=='storage': settings.evaluation_run_storage_mb=0
    run=queue(store,settings,max_seconds=1 if limit=='deadline' else 900)
    Worker(settings).run(True)
    saved=store.get_run(run['id'])
    assert saved['status']=='failed',saved
    assert saved['failure_reason']==reason,saved
