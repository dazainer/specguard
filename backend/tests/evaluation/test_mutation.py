import json

import pytest

from app.evaluation.mutation import parse_inventory, outcome, mutation_sources
from app.evaluation.mutation_cache import cache_key
from tests.evaluation.test_evaluate import execution, IMAGE


@pytest.mark.parametrize('result, expected', [
    (execution(), 'survived'), (execution('failed',passed=1,failed=1), 'killed'),
    (execution('timeout'), 'timed_out'), (execution('resource_limit'), 'errors'),
    (execution('infrastructure_error'), 'errors'), (execution('collection_error'), 'errors'),
    (execution(passed=1,skipped=1), 'suspicious'), (execution(missing=True), 'suspicious'),
    (execution(count=3,passed=3), 'suspicious'),
])
def test_normalized_outcomes(result, expected):
    assert outcome(result,2) == expected


def test_inventory_fixture_is_strict():
    from pathlib import Path
    fixture=Path(__file__).parents[1]/'fixtures/mutmut-2.4.4.json'
    raw=execution().model_copy(update={'stdout':fixture.read_text()})
    parsed=parse_inventory(raw,['src/reservations.py'])
    assert len(parsed)==1 and parsed[0].operator=='number'
    with pytest.raises(ValueError):
        parse_inventory(raw,['src/other.py'])
    data=json.loads(raw.stdout)
    data['mutants']*=2
    with pytest.raises(ValueError):
        parse_inventory(raw.model_copy(update={'stdout':json.dumps(data)}),['src/reservations.py'])
    with pytest.raises(ValueError):
        parse_inventory(raw.model_copy(update={'output_truncated':True}),['src/reservations.py'])


def test_mutation_exclusions(manifest,tmp_path):
    (tmp_path/'src').mkdir()
    (tmp_path/'src/a.py').write_text('a=1')
    (tmp_path/'src/b.py').write_text('b=2')
    configured=manifest.model_copy(update={'mutation':manifest.mutation.model_copy(update={'source_paths':['src'],'excluded_paths':['src/b.py']})})
    assert mutation_sources(configured,tmp_path)==['src/a.py']


def test_native_cache_identity_includes_tests_source_image_and_configuration(tmp_path):
    from app.schemas.execution import ExecutionRequest
    source=tmp_path/'target'; tests=tmp_path/'tests'
    source.mkdir(); tests.mkdir()
    (source/'module.py').write_text('VALUE=1')
    (tests/'test_it.py').write_text('def test_it(): pass')
    request=ExecutionRequest(target_snapshot=source,source_paths=['module.py'],test_workspace=tests,test_paths=['test_it.py'])
    key=cache_key(request,IMAGE,'inventory','config','commit')
    assert key != cache_key(request,'sha256:'+'c'*64,'inventory','config','commit')
    assert key != cache_key(request,IMAGE,'inventory','different-config','commit')
    (tests/'test_it.py').write_text('def test_it(): assert True')
    assert key != cache_key(request,IMAGE,'inventory','config','commit')


def test_cache_round_trip_preserves_evidence_and_rejects_corruption(tmp_path):
    from pathlib import Path
    from app.evaluation.mutation_cache import read_cache, write_cache
    from app.schemas.evaluation import MutationSummary
    raw=execution().model_copy(update={'stdout':(Path(__file__).parents[1]/'fixtures/mutmut-2.4.4.json').read_text()})
    mutants=parse_inventory(raw,['src/reservations.py'])
    summary=MutationSummary(inventory_sha256='a'*64,configuration_sha256='b'*64,generated=1,killed=1,survived=0,
        timed_out=0,invalid=0,errors=0,suspicious=0,denominator=1,score=1.0,duration_seconds=30.0)
    records=tmp_path/'records.jsonl'
    records.write_text(json.dumps({'id':mutants[0].id,'status':'killed'})+'\n')
    cache=tmp_path/'cache'
    write_cache(cache,'key',summary,records,'source-run')
    loaded, metadata=read_cache(cache,'key',mutants,tmp_path/'reused.jsonl')
    assert loaded.killed == 1 and metadata['source_run']=='source-run'
    assert metadata['original_duration_seconds']==30.0 and loaded.duration_seconds < 30
    assert (tmp_path/'reused.jsonl').read_bytes()==records.read_bytes()
    data=json.loads((cache/'key.json').read_text())
    data['records']='corrupted'
    (cache/'key.json').write_text(json.dumps(data))
    assert read_cache(cache,'key',mutants,tmp_path/'bad.jsonl') is None


def test_cache_never_reuses_ambiguous_or_timed_out_results(tmp_path):
    from app.evaluation.mutation_cache import write_cache
    from app.schemas.evaluation import MutationSummary
    summary=MutationSummary(inventory_sha256='a'*64,configuration_sha256='b'*64,generated=1,killed=0,survived=0,
        timed_out=1,invalid=0,errors=0,suspicious=0,denominator=0,score=None,duration_seconds=2.0)
    write_cache(tmp_path/'cache','key',summary,tmp_path/'missing-records','run')
    assert not (tmp_path/'cache').exists()
