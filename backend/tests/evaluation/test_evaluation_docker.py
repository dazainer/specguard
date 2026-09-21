"""The fake provider exercises the real end-to-end pipeline, exclusively in Docker."""
import json
import os
from pathlib import Path
import shutil

import pytest
import yaml

from app.evaluation.evaluate import evaluate, request_for
from app.evaluation.execution_runner import DockerRunner
from app.evaluation.manifest import load_manifest
from app.evaluation.mutation import parse_inventory
from app.evaluation.prepare import prepare
from app.evaluation.providers import Completion

pytestmark = [pytest.mark.docker, pytest.mark.skipif(os.environ.get('SPECGUARD_DOCKER_TESTS') != '1', reason='opt-in Docker verification')]


@pytest.mark.parametrize('subject_name', ['first_subject','pagination','shipping','access_policy','intervals'])
async def test_complete_fixture_benchmark(subject, subject_name, tmp_path):
    root = subject.parent / subject_name
    report = await evaluate(root/'specguard.yaml',tmp_path/'run',os.environ['SPECGUARD_RUNNER_IMAGE'])
    assert report.status == 'completed', report.failure_reason
    assert report.generated.mutation.inventory_sha256 == report.native.mutation.inventory_sha256
    assert report.generated.mutation.generated == report.native.mutation.generated > 0
    assert all(run.status == 'passed' for run in report.generated.baseline_runs)


def test_inventory_reproduces_exactly_without_importing_source(subject, tmp_path):
    prepare(subject/'specguard.yaml',tmp_path/'prepared',fixture=subject/'generation-fixture.json')
    manifest=load_manifest(subject/'specguard.yaml')
    request=request_for(manifest,tmp_path/'prepared','native').model_copy(update={'mode':'inventory','mutation_paths':['src/reservations.py']})
    runner=DockerRunner(os.environ['SPECGUARD_RUNNER_IMAGE'])
    first, second = runner.run(request), runner.run(request)
    assert first.stdout == second.stdout
    assert len(parse_inventory(first,['src/reservations.py'])) == 52


@pytest.mark.parametrize('content, reason', [
    ('def test_bad():\n    assert False\n','generated_baseline_failed'),
    ('import pytest\n@pytest.mark.skip\ndef test_skip(): pass\n','generated_baseline_failed'),
    ('while True: pass\n','generated_collection_timeout'),
])
async def test_bad_generated_output_is_rejected_inside_container(subject,tmp_path,content,reason):
    root=tmp_path/'subject'
    shutil.copytree(subject,root)
    data=yaml.safe_load((root/'specguard.yaml').read_text())
    data['tests']['timeout_seconds']=1
    (root/'specguard.yaml').write_text(yaml.safe_dump(data))
    class Provider:
        async def complete(self,*args):
            return Completion(json.dumps({'files':[{'path':'.specguard/generated_tests/test_bad.py','content':content}]}))
    report=await evaluate(root/'specguard.yaml',tmp_path/'run',os.environ['SPECGUARD_RUNNER_IMAGE'],provider=Provider())
    assert report.status == 'failed' and report.failure_reason == reason
    assert report.generated.mutation is None
    assert (tmp_path/'run/quarantine').exists()
