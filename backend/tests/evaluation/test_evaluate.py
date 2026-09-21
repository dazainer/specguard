import json

import pytest

from app.evaluation.evaluate import evaluate, gate_suite, request_for
from app.evaluation.providers import Completion
from app.schemas.execution import ExecutionResult

IMAGE = 'sha256:' + 'b' * 64


def execution(status='passed', *, count=2, passed=2, failed=0, skipped=0, errors=0, missing=False):
    counts = dict(collected=count, passed=passed, failed=failed, skipped=skipped, errors=errors)
    return ExecutionResult(status=status, exit_code=0 if status=='passed' else 1, duration_seconds=0.1,
        stdout='' if missing else 'SPECGUARD_PYTEST_JSON='+json.dumps(counts), container_name='fake-job',
        image_digest=IMAGE, runtime={'python':'3.12.13','pytest':'8.3.0','mutmut':'2.4.4'})


class FakeRunner:
    def __init__(self, results):
        self.results = iter(results)
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return next(self.results)


@pytest.mark.parametrize('results, failure', [
    ([execution(passed=0),execution(),execution()], None),
    ([execution(count=0,passed=0)], 'collection_invalid_observations'),
    ([execution('collection_error',passed=0)], 'collection_collection_error'),
    ([execution('timeout',missing=True)], 'collection_timeout'),
    ([execution(missing=True)], 'collection_invalid_observations'),
    ([execution(passed=0),execution('failed',passed=1,failed=1),execution('failed',passed=1,failed=1)], 'baseline_failed'),
    ([execution(passed=0),execution(),execution('failed',passed=1,failed=1)], 'baseline_flaky'),
    ([execution(passed=0),execution(passed=1,skipped=1),execution(passed=1,skipped=1)], 'baseline_failed'),
    ([execution(passed=0),execution(count=1,passed=1),execution(count=1,passed=1)], 'baseline_failed'),
    ([execution(passed=0),execution('resource_limit'),execution('resource_limit')], 'baseline_resource_limit'),
])
def test_baseline_whole_suite_gate(results, failure, manifest, tmp_path):
    runner = FakeRunner(results)
    suite, reason = gate_suite(runner, request_for(manifest,tmp_path,'generated'),2,tmp_path,'generated')
    assert reason == failure
    assert suite.mutation is None
    if reason is None:
        assert suite.accepted_tests == 2 and suite.rejected_tests == 0
    elif suite.collection_status == 'passed':
        assert suite.accepted_tests == 0 and suite.rejected_tests == 2


class Provider:
    def __init__(self, text):
        self.text = text
    async def complete(self, *args):
        return Completion(self.text)


async def test_same_pipeline_prepares_generates_and_baselines(subject, tmp_path):
    runner = FakeRunner([execution(passed=0),execution(),execution()] * 2)
    output = tmp_path/'run'
    report = await evaluate(subject/'specguard.yaml',output,IMAGE,
        provider=Provider((subject/'generation-fixture.json').read_text()),runner=runner,mutate=False)
    assert report.status == 'completed'
    assert report.provenance.python_version == '3.12.13'
    assert report.generated.accepted_tests == 2 and report.native.accepted_tests == 2
    assert len(runner.requests) == 6
    assert all('tests' not in request.source_paths for request in runner.requests)
    assert (output/'summary.csv').exists() and (output/'summary.md').exists()
    assert (output/'prompt.json').exists() and (output/'attempts.json').exists()


async def test_failing_generated_suite_is_quarantined_and_never_mutated(subject,tmp_path):
    runner = FakeRunner([execution(passed=0),execution('failed',failed=1),execution()])
    output = tmp_path/'failed-run'
    report = await evaluate(subject/'specguard.yaml',output,IMAGE,
        provider=Provider((subject/'generation-fixture.json').read_text()),runner=runner)
    assert report.status == 'failed' and report.failure_reason == 'generated_baseline_flaky'
    assert report.generated.mutation is None and report.native.mutation is None
    assert (output/'quarantine').exists() and not (output/'generated').exists()
    assert len(runner.requests) == 3


async def test_exception_keeps_failed_report_without_secret_message(subject,tmp_path):
    class Broken:
        def run(self, request):
            raise RuntimeError('secret-internal-data')
    output=tmp_path/'broken'
    report=await evaluate(subject/'specguard.yaml',output,IMAGE,
        provider=Provider((subject/'generation-fixture.json').read_text()),runner=Broken())
    assert report.status == 'failed' and report.failure_reason == 'RuntimeError'
    assert 'secret-internal-data' not in (output/'report.json').read_text()
