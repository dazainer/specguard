"""Opt-in tests. Payloads are text and are executed only by DockerRunner."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from app.evaluation.execution_runner import DockerRunner
from app.evaluation.manifest import ResourceLimits
from app.evaluation.prepare import prepare
from app.schemas.execution import ExecutionRequest

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(os.environ.get("SPECGUARD_DOCKER_TESTS") != "1", reason="opt-in Docker verification"),
]
FIXTURES = Path(__file__).parents[1] / "fixtures/runner"


@pytest.fixture
def docker_runner():
    image = os.environ.get("SPECGUARD_RUNNER_IMAGE")
    assert image, "Set SPECGUARD_RUNNER_IMAGE to the pinned image ID when opting in"
    return DockerRunner(image)


@pytest.fixture
def run_case(tmp_path, docker_runner, monkeypatch):
    monkeypatch.setenv("SPECGUARD_HOST_SENTINEL", "host-only-nonsecret-canary")
    source = tmp_path / "source"
    tests = tmp_path / "tests"
    (source / "src").mkdir(parents=True)
    (source / "src/marker.py").write_text("MARKER = 'unchanged'\n")
    tests.mkdir()

    def run(name, timeout=10, mode="run"):
        (tests / "test_case.py").write_bytes((FIXTURES / f"{name}.txt").read_bytes())
        request = ExecutionRequest(
            target_snapshot=source, test_workspace=tests, source_paths=["src"], test_paths=["test_case.py"],
            mode=mode, timeout_seconds=timeout,
            limits=ResourceLimits(memory_mb=128, cpus=0.5, pids=32, output_kb=16, scratch_mb=16, file_size_mb=1),
        )
        result = docker_runner.run(request)
        assert result.cleanup_succeeded, result.model_dump_json()
        assert (source / "src/marker.py").read_text() == "MARKER = 'unchanged'\n"
        # Verify the daemon actually removed this particular owned container.
        check = subprocess.run(["docker", "container", "ls", "--all", "--filter", f"name=^/{result.container_name}$", "--format", "{{.ID}}"], capture_output=True, text=True, check=True, timeout=10)
        assert not check.stdout.strip()
        report_dir = os.environ.get("SPECGUARD_DOCKER_RESULTS")
        if report_dir:
            directory = Path(report_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{name}-{mode}.json").write_text(result.model_dump_json(indent=2))
        return result

    return run


@pytest.mark.parametrize("name, expected", [
    ("normal", "passed"), ("failure", "failed"), ("collection_error", "collection_error"),
    ("isolation", "passed"), ("processes", "passed"), ("memory", "resource_limit"),
    ("crash", "failed"),
])
def test_container_outcomes(run_case, name, expected):
    result = run_case(name)
    assert result.status == expected, result.model_dump_json()
    if name == "memory":
        assert result.oom_killed


@pytest.mark.parametrize("name, mode", [("infinite_loop", "run"), ("collection_hang", "collect"), ("ignore_signals", "run")])
def test_timeouts(run_case, name, mode):
    result = run_case(name, timeout=2, mode=mode)
    assert result.status == "timeout", result.model_dump_json()
    assert result.duration_seconds < 15


def test_collect_only(run_case):
    result = run_case("normal", mode="collect")
    assert result.status == "passed", result.model_dump_json()
    assert "container fixture passed" not in result.stdout
    assert "test_normal" in result.stdout


def test_output_flood_is_drained_and_capped(run_case):
    result = run_case("output_flood")
    assert result.status == "passed", result.model_dump_json()
    assert result.output_truncated and result.output_bytes_seen >= 2 * 1024 * 1024
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 16 * 1024


def test_native_and_generated_benchmark_independently(docker_runner, subject, tmp_path):
    prepared = tmp_path / "prepared"
    prepare(subject / "specguard.yaml", prepared, fixture=subject / "generation-fixture.json")
    for suite in ("native", "generated"):
        request = ExecutionRequest(
            target_snapshot=prepared / "target", source_paths=["src"],
            test_workspace=prepared / ("target" if suite == "native" else "generated"),
            test_paths=["tests" if suite == "native" else ".specguard/generated_tests"],
        )
        result = docker_runner.run(request)
        assert result.status == "passed", result.model_dump_json()
        assert ("30 passed" if suite == "native" else "7 passed") in result.stdout


def test_native_config_and_conftest_cannot_leak_into_generated_suite(docker_runner, tmp_path):
    target = tmp_path / "target"
    generated = tmp_path / "generated"
    (target / "src").mkdir(parents=True)
    (target / "src/answer.py").write_text("ANSWER = 42\n")
    (target / "native").mkdir()
    (target / "native/test_leak.py").write_text("raise RuntimeError('native test leaked')")
    (target / "conftest.py").write_text("raise RuntimeError('native conftest leaked')")
    (target / "pytest.ini").write_text("[pytest]\naddopts = native\n")
    (generated / "suite").mkdir(parents=True)
    (generated / "suite/conftest.py").write_text("raise RuntimeError('conftest loaded')")
    (generated / "suite/test_generated.py").write_text("from src.answer import ANSWER\ndef test_generated():\n    assert ANSWER == 42\n")
    result = docker_runner.run(ExecutionRequest(target_snapshot=target, source_paths=["src"], test_workspace=generated, test_paths=["suite"]))
    assert result.status == "passed" and "1 passed" in result.stdout, result.model_dump_json()
