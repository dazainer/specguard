"""Rebuild subset bundles from hash-verified mirrors; never import upstream code."""
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
builder = runpy.run_path(str(ROOT.parent/'subjects/first_subject/rebuild_bundle.py'))['rebuild']

if __name__ == '__main__':
    for subject in sorted(ROOT.glob('boltons_*')):
        upstream = json.loads((subject/'upstream.json').read_text())
        for relative, expected in upstream['sha256'].items():
            actual = hashlib.sha256((subject/'target'/relative).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f'Upstream mirror changed: {relative}')
        module = subject.name.removeprefix('boltons_')
        builder(subject, title=f"Unmodified boltons {module} subset from {upstream['upstream_commit']}")
