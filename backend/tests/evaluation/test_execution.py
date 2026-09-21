import json
import os
from pathlib import Path
import stat
import subprocess

import pytest
from pydantic import ValidationError

from app.evaluation import execution_runner as runner
from app.evaluation.execution_output import OutputBuffer
from app.evaluation.execution_workspace import stage_selection
from app.schemas.execution import ExecutionRequest

IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def request_data(tmp_path):
    source = tmp_path / "target"
    tests = tmp_path / "generated"
    source.mkdir()
    tests.mkdir()
    (source / "module.py").write_text("answer = 42\n")
    (tests / "test_example.py").write_text("def test_example():\n    assert True\n")
    return dict(target_snapshot=source, test_workspace=tests, source_paths=["module.py"], test_paths=["test_example.py"])


@pytest.mark.parametrize("change", [
    {"test_paths": ["../secret.py"]}, {"test_paths": ["/etc/passwd"]},
    {"test_paths": []}, {"test_paths": ["tests", "tests/test_a.py"]},
    {"source_paths": ["source", "SOURCE"]}, {"timeout_seconds": 0},
    {"command": ["sh", "-c", "echo unsafe"]}, {"command": ["pytest", "native_tests"]},
    {"environment": {"SECRET": "not allowed"}},
])
def test_request_rejects_unsafe_options(request_data, change):
    with pytest.raises(ValidationError):
        ExecutionRequest(**(request_data | change))


def test_source_cannot_include_selected_native_tests(request_data):
    request_data.update(test_workspace=request_data["target_snapshot"], source_paths=["tests"], test_paths=["tests/test_a.py"])
    with pytest.raises(ValidationError):
        ExecutionRequest(**request_data)


def test_docker_command_has_all_controls(request_data, tmp_path):
    request = ExecutionRequest(**request_data)
    command = runner.create_arguments(request, IMAGE, "owned-container", tmp_path)
    for flag, value in {
        "--network": "none", "--ipc": "none", "--user": "65532:65532", "--cap-drop": "ALL",
        "--security-opt": "no-new-privileges=true", "--memory": "1024m", "--memory-swap": "1024m",
        "--pids-limit": "128", "--cpus": "1.0", "--log-driver": "none", "--restart": "no",
        "--cgroupns": "private", "--pull=never": None,
    }.items():
        assert flag in command
        if value is not None:
            assert command[command.index(flag) + 1] == value
    assert "--read-only" in command
    assert "fsize=16777216:16777216" in command
    mounts = [command[i + 1] for i, part in enumerate(command) if part == "--mount"]
    assert len(mounts) == 2 and all("readonly" in mount and "bind-recursive=disabled" in mount for mount in mounts)
    assert not any(str(request_data["target_snapshot"]) in mount for mount in mounts)
    assert "--privileged" not in command and "seccomp=unconfined" not in command
    assert "--entrypoint" in command and "/usr/bin/timeout" in command
    assert command[-1] == "/tests/test_example.py"


def test_staging_copies_only_selected_files(request_data, tmp_path):
    root = request_data["target_snapshot"]
    (root / ".env").write_text("SECRET=do-not-copy")
    (root / "native_tests").mkdir()
    (root / "native_tests/test_native.py").write_text("raise RuntimeError('must not run')")
    destination = tmp_path / "stage"
    stage_selection(root, ["module.py"], destination)
    assert [path.name for path in destination.iterdir()] == ["module.py"]
    assert (destination / "module.py").read_text() == "answer = 42\n"
    assert stat.S_IMODE((destination / "module.py").stat().st_mode) == 0o444


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "secret", "mixed_case_secret", "oversized"])
def test_staging_rejects_unsafe_files(request_data, tmp_path, kind):
    root = request_data["target_snapshot"]
    root.joinpath("module.py").unlink()
    if kind == "symlink":
        root.joinpath("module.py").symlink_to(tmp_path / "outside")
    elif kind == "hardlink":
        (root / "original").write_text("pass")
        os.link(root / "original", root / "module.py")
    elif kind == "fifo":
        os.mkfifo(root / "module.py")
    elif kind in {"secret", "mixed_case_secret"}:
        root.joinpath("module.py").mkdir()
        root.joinpath("module.py", ".env" if kind == "secret" else ".ENV.local").write_text("secret")
    else:
        with (root / "module.py").open("wb") as file:
            file.truncate(4 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        stage_selection(root, ["module.py"], tmp_path / "stage")


def test_output_is_combined_bounded_and_sanitized():
    output = OutputBuffer(32)
    output.add("stdout", b"\x1b[31mhello\x1b[0m\x00\n")
    output.add("stderr", b"x" * 1000)
    assert output.truncated and output.seen > 1000
    assert output.text("stdout") == "hello\n"
    assert sum(len(output.text(stream).encode()) for stream in ("stdout", "stderr")) <= 32


def test_invalid_utf8_does_not_expand_output_budget():
    output = OutputBuffer(9)
    output.add("stdout", b"\xff" * 100)
    assert len(output.text("stdout").encode()) <= 9


@pytest.mark.parametrize("code, oom, timed_out, expected", [
    (0, False, False, "passed"), (1, False, False, "failed"),
    (2, False, False, "collection_error"), (5, False, False, "collection_error"),
    (3, False, False, "infrastructure_error"), (127, False, False, "infrastructure_error"),
    (124, False, False, "timeout"), (137, True, False, "resource_limit"),
    (137, False, False, "failed"), (153, False, False, "resource_limit"),
    (139, False, False, "failed"), (137, False, True, "timeout"),
    (137, True, True, "resource_limit"),
])
def test_status_classification(code, oom, timed_out, expected):
    assert runner.classify({"Status": "exited", "ExitCode": code, "OOMKilled": oom}, timed_out)[0] == expected


@pytest.mark.parametrize("elapsed, expected", [(0.5, "failed"), (3.0, "timeout")])
def test_forced_kill_classification_uses_deadline(elapsed, expected):
    state = {"Status": "exited", "ExitCode": 137, "OOMKilled": False}
    assert runner.classify(state, False, elapsed_seconds=elapsed, timeout_seconds=2)[0] == expected


@pytest.mark.parametrize("image", ["python:latest", "specguard-runner:phase2", "sha256:abc", "--privileged"])
def test_floating_images_rejected(image):
    with pytest.raises(ValueError):
        runner.DockerRunner(image)


def test_local_endpoint_rejects_remote_daemon(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, b"tcp://remote:2375\n"))
    with pytest.raises(runner.RunnerError, match="local Unix"):
        runner.local_endpoint()


@pytest.mark.parametrize("failure", [None, "create", "attach", "inspect", "cleanup"])
def test_lifecycle_always_cleans_owned_container_and_workspace(request_data, monkeypatch, failure):
    calls = []
    workspaces = []
    docker = runner.DockerRunner(IMAGE)
    monkeypatch.setattr(runner, "local_endpoint", lambda: "unix:///unused.sock")
    monkeypatch.setattr(docker, "_runtime", lambda client: {"docker": "fake"})

    def control(client, *args, **kwargs):
        calls.append(args)
        workspaces.append(Path(client[2]).parent)
        assert not Path(client[2], "config.json").exists()
        if args[0] == "create" and failure == "create":
            raise runner.RunnerError("create failed")
        if args[0] == "inspect":
            if failure == "inspect":
                raise runner.RunnerError("inspect failed")
            return json.dumps({"Status": "exited", "ExitCode": 0, "OOMKilled": False}).encode()
        if args[0] == "rm" and failure in {"create", "cleanup"}:
            raise runner.RunnerError("remove failed")
        if args[0] == "container":
            return b"" if failure == "create" else b"still-present"
        return b"owned-id"

    def attach(*args):
        if failure == "attach":
            raise runner.RunnerError("attach failed")
        return False

    monkeypatch.setattr(docker, "_control", control)
    monkeypatch.setattr(docker, "_attach", attach)
    result = docker.run(ExecutionRequest(**request_data))
    assert result.status == ("passed" if failure is None else "infrastructure_error")
    assert ("rm", "--force", result.container_name) in calls
    assert not any(path.exists() for path in workspaces)
    assert result.cleanup_succeeded is (failure != "cleanup")


def test_client_environment_does_not_forward_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "host-canary")
    monkeypatch.setenv("HTTP_PROXY", "http://credential-proxy")
    assert set(runner.minimal_env()) == {"PATH"}
