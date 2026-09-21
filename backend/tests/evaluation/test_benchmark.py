import json
from pathlib import Path

import pytest

from app.evaluation.benchmark import summarize
from app.evaluation.prepare import prepare


@pytest.mark.parametrize('name',['first_subject','pagination','shipping','access_policy','intervals'])
def test_pinned_subject_matches_reviewable_mirror(name,subject,tmp_path):
    root=subject.parent/name
    report=prepare(root/'specguard.yaml',tmp_path/'run',fixture=root/'generation-fixture.json')
    assert report.status == 'prepared'
    target=tmp_path/'run/target'
    for path in (root/'target').rglob('*'):
        if path.is_file():
            assert (target/path.relative_to(root/'target')).read_bytes() == path.read_bytes()
    context=json.loads((tmp_path/'run/context.json').read_text())
    assert all(not name.startswith('tests/') for name in context['source_files'])


def test_aggregate_keeps_failed_trials_and_reports_variance(tmp_path):
    records=[dict(subject='s',provider='fixture',strategy='contract-v1',status='completed',failure_reason=None,generated_score=0.5,duration_seconds=1.0),
             dict(subject='s',provider='fixture',strategy='contract-v1',status='failed',failure_reason='baseline_failed',generated_score=None,duration_seconds=2.0),
             dict(subject='s',provider='fixture',strategy='contract-v1',status='completed',failure_reason=None,generated_score=1.0,duration_seconds=3.0)]
    summarize(tmp_path,records,{'provider':'fixture'})
    group=json.loads((tmp_path/'aggregates.json').read_text())[0]
    assert group['attempted']==3 and group['completed']==2 and group['score_n']==2
    assert group['score_mean']==0.75 and group['score_variance']==0.0625
    assert json.loads((tmp_path/'failures.json').read_text())=={'baseline_failed':1}
