"""Private curated evaluation API; no arbitrary repository/path/command execution."""
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.evaluation.manifest import load_manifest
from app.evaluation.paths import safe_path
from app.evaluation.public_data import scrub
from app.evaluation.store import Store, Conflict

router=APIRouter(prefix='/api/evaluations',tags=['Evaluations'])


def get_store():
    store=Store(get_settings().evaluation_db)
    if not store.ready()['database']:
        raise HTTPException(503,'Evaluation database needs migrations')
    return store


class TargetInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str=Field(min_length=1,max_length=100)
    subject: str=Field(pattern=r'^[a-z0-9_]{1,64}$')


class RunInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target_id: str=Field(min_length=36,max_length=36)
    idempotency_key: str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')
    strategy: Literal['contract-v1','boundary-v1']='contract-v1'
    baseline_only: bool=False
    max_seconds: int=Field(default=900,ge=10,le=3600)


def public_run(run):
    result={key:value for key,value in run.items() if key not in {'owner','idempotency_key','request_hash','report_json','options_json','timings_json'}}
    result['options']=json.loads(run['options_json'])
    result['report']=json.loads(run['report_json']) if run['report_json'] else None
    result['timings']=json.loads(run['timings_json']) if run['timings_json'] else None
    result['queue_seconds']=(run['started_at'] or run['finished_at'] or time.time())-run['created_at']
    return scrub(result,get_settings().openai_api_key)


def require_run(store, run_id):
    run=store.get_run(run_id)
    if not run:
        raise HTTPException(404,'Evaluation run not found')
    return run


@router.get('/catalog')
def catalog():
    root=get_settings().evaluation_subjects.resolve()
    rows=[]
    for path in sorted(root.glob('*/specguard.yaml')):
        if path.parent.is_symlink() or path.is_symlink():
            continue
        manifest=load_manifest(path)
        rows.append(dict(subject=path.parent.name,commit=manifest.repository.commit,provider='fixture'))
    return rows


@router.get('/targets')
def targets(store: Store=Depends(get_store)):
    return [dict(id=row['id'],name=row['name'],subject=row['subject'],created_at=row['created_at'],manifest=json.loads(row['manifest_json']))
            for row in store.rows('SELECT * FROM targets ORDER BY created_at DESC LIMIT 100')]


@router.post('/targets',status_code=201)
def create_target(data: TargetInput,store: Store=Depends(get_store)):
    try:
        path=safe_path(get_settings().evaluation_subjects.resolve(),data.subject+'/specguard.yaml',must_exist=True)
        manifest=load_manifest(path)
    except (ValueError,OSError):
        raise HTTPException(400,'Select an installed curated subject')
    row=store.add_target(data.name,data.subject,manifest.model_dump())
    return dict(id=row['id'],name=row['name'],subject=row['subject'],manifest=manifest.model_dump())


@router.get('/targets/{target_id}')
def target(target_id: str,store: Store=Depends(get_store)):
    rows=store.rows('SELECT * FROM targets WHERE id=?',(target_id,))
    if not rows:
        raise HTTPException(404,'Target not found')
    return dict(id=rows[0]['id'],name=rows[0]['name'],subject=rows[0]['subject'],manifest=json.loads(rows[0]['manifest_json']))


@router.post('/runs',status_code=202)
def start_run(data: RunInput,store: Store=Depends(get_store)):
    image=get_settings().evaluation_runner_image
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',image):
        raise HTTPException(503,'Configure an immutable evaluation runner image ID')
    try:
        return public_run(store.enqueue(data.target_id,dict(strategy=data.strategy,baseline_only=data.baseline_only),data.idempotency_key,image,data.max_seconds))
    except Conflict as error:
        raise HTTPException(409,str(error))
    except KeyError:
        raise HTTPException(404,'Target not found')


@router.get('/runs')
def runs(limit: int=Query(50,ge=1,le=100),store: Store=Depends(get_store)):
    return [public_run(row) for row in store.rows('SELECT * FROM runs ORDER BY created_at DESC LIMIT ?',(limit,))]


@router.get('/runs/{run_id}')
def run(run_id: str,store: Store=Depends(get_store)):
    result=public_run(require_run(store,run_id))
    result['events']=store.rows('SELECT stage,at FROM events WHERE run_id=? ORDER BY id',(run_id,))
    return result


@router.post('/runs/{run_id}/cancel')
def cancel(run_id: str,store: Store=Depends(get_store)):
    try:
        return public_run(store.cancel(run_id))
    except KeyError:
        raise HTTPException(404,'Run not found')


@router.get('/runs/{run_id}/artifacts')
def artifacts(run_id: str,store: Store=Depends(get_store)):
    require_run(store,run_id)
    return store.rows('SELECT path,sha256,size_bytes,accepted FROM artifacts WHERE run_id=?',(run_id,))


@router.get('/runs/{run_id}/artifact')
def artifact(run_id: str,path: str,store: Store=Depends(get_store)):
    row=require_run(store,run_id)
    if row['pruned']:
        raise HTTPException(410,'Raw artifacts expired under retention policy')
    if not store.rows('SELECT 1 FROM artifacts WHERE run_id=? AND path=?',(run_id,path)):
        raise HTTPException(404,'Artifact not found')
    root=get_settings().evaluation_artifacts.resolve()/run_id
    directory='quarantine' if (root/'quarantine').exists() else 'generated'
    try:
        content=safe_path(root/directory,path,must_exist=True).read_text()
    except (ValueError,OSError):
        raise HTTPException(404,'Artifact unavailable')
    return dict(path=path,content=scrub(content,get_settings().openai_api_key,262144),scrubbed=True)


@router.get('/runs/{run_id}/mutants')
def mutants(run_id: str,suite: Literal['native','generated']='generated',
            status: Literal['killed','survived','timed_out','invalid','errors','suspicious']|None=None,
            offset: int=Query(0,ge=0),limit: int=Query(25,ge=1,le=100),store: Store=Depends(get_store)):
    row=require_run(store,run_id)
    if row['pruned']:
        raise HTTPException(410,'Mutant details expired under retention policy')
    where='run_id=? AND suite=?'
    params=[run_id,suite]
    if status:
        where+=' AND status=?'; params.append(status)
    total=store.rows('SELECT count(*) AS total FROM mutants WHERE '+where,params)[0]['total']
    rows=store.rows('SELECT data_json FROM mutants WHERE '+where+' ORDER BY mutant_id LIMIT ? OFFSET ?',params+[limit,offset])
    return dict(total=total,items=scrub([json.loads(row['data_json']) for row in rows],get_settings().openai_api_key))


@router.get('/runs/{run_id}/logs')
def logs(run_id: str,store: Store=Depends(get_store)):
    row=require_run(store,run_id)
    if row['pruned']:
        raise HTTPException(410,'Execution logs expired under retention policy')
    root=get_settings().evaluation_artifacts.resolve()/run_id
    logs=[]
    for path in sorted(root.glob('*-collection.json'))+sorted(root.glob('*-baseline-*.json')):
        if path.is_symlink() or path.stat().st_size > 20*1024*1024:
            continue
        try:
            value=json.loads(path.read_text())
        except (ValueError,OSError):
            # A polling read may overlap a bounded execution-artifact write.
            continue
        logs.append(dict(stage=path.stem,status=value['status'],stdout=scrub(value['stdout'],get_settings().openai_api_key),
                         stderr=scrub(value['stderr'],get_settings().openai_api_key),output_truncated=value['output_truncated'] or len(value['stdout'].encode())>16384 or len(value['stderr'].encode())>16384))
    return logs


@router.get('/runs/{run_id}/export')
def export(run_id: str,format: Literal['json','md','csv']='json',store: Store=Depends(get_store)):
    row=require_run(store,run_id)
    if not row['report_json']:
        raise HTTPException(409,'A report is not available yet')
    if format=='json':
        content=json.dumps(scrub(json.loads(row['report_json']),get_settings().openai_api_key),indent=2)
    else:
        if row['pruned']:
            raise HTTPException(410,'Rendered report expired; JSON is retained')
        path=get_settings().evaluation_artifacts.resolve()/run_id/f'summary.{format}'
        if not path.exists():
            raise HTTPException(409,'Rendered report not ready')
        content=scrub(path.read_text(),get_settings().openai_api_key,262144)
    return Response(content,media_type={'json':'application/json','md':'text/markdown','csv':'text/csv'}[format],
                    headers={'Content-Disposition':f'attachment; filename="evaluation-{run_id}.{format}"'})


@router.get('/ready')
def ready():
    status=Store(get_settings().evaluation_db).ready()
    status['image_configured']=bool(re.fullmatch(r'sha256:[a-f0-9]{64}',get_settings().evaluation_runner_image))
    return Response(json.dumps(status),status_code=200 if all(status.values()) else 503,media_type='application/json')


@router.get('/metrics')
def metrics(store: Store=Depends(get_store)):
    stages={}
    for row in store.rows('SELECT timings_json FROM runs WHERE timings_json IS NOT NULL'):
        for stage,seconds in json.loads(row['timings_json']).items():
            observed=stages.setdefault(stage,dict(count=0,total_seconds=0.0))
            observed['count']+=1
            observed['total_seconds']+=seconds
    for observed in stages.values():
        observed['mean_seconds']=observed['total_seconds']/observed['count']
    return dict(states=store.rows('SELECT status,count(*) AS count FROM runs GROUP BY status'),
                stage_durations=stages,
                failures=store.rows("SELECT failure_reason,count(*) AS count FROM runs WHERE status='failed' GROUP BY failure_reason"),
                queue=store.rows('SELECT avg(started_at-created_at) AS mean_seconds FROM runs WHERE started_at IS NOT NULL')[0],
                mutant_outcomes=store.rows('SELECT status,count(*) AS count FROM mutants GROUP BY status'))
