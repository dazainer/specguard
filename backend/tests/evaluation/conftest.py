from pathlib import Path

import pytest

from app.evaluation.manifest import load_manifest


@pytest.fixture
def subject():
    return Path(__file__).resolve().parents[3] / "benchmarks/subjects/first_subject"


@pytest.fixture
def manifest(subject):
    return load_manifest(subject / "specguard.yaml")
