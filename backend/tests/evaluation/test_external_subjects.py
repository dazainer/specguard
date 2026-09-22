import hashlib
import json
from pathlib import Path

import pytest

from app.evaluation.prepare import prepare


@pytest.mark.parametrize('module', ['mathutils', 'typeutils'])
def test_external_subset_preserves_upstream_hashes_and_prepares_offline(module, tmp_path):
    root = Path(__file__).resolve().parents[3]/'benchmarks/external'/('boltons_'+module)
    provenance = json.loads((root/'upstream.json').read_text())
    for relative, digest in provenance['sha256'].items():
        assert hashlib.sha256((root/'target'/relative).read_bytes()).hexdigest() == digest
    output = tmp_path/'prepared'
    report = prepare(root/'specguard.yaml', output, fixture=root/'generation-fixture.json')
    assert report.status == 'prepared'
    context = json.loads((output/'context.json').read_text())
    assert 'tests/test_' not in json.dumps(context)
    assert report.provenance.repository_commit != provenance['upstream_commit']
