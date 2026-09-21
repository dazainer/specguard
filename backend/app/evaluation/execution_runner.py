"""Synchronous local Docker runner. All target/test execution is container-only."""

import csv
import io
import json
import os
import re
import selectors
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from app.evaluation.execution_output import OutputBuffer, sanitize
from app.evaluation.execution_workspace import stage_selection
from app.evaluation.control import EvaluationStopped
from app.schemas.execution import ExecutionRequest, ExecutionResult


class RunnerError(Exception):
    pass


def minimal_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}


def local_endpoint() -> str:
    try:
        result = subprocess.run(
            ["docker", "--config", str(Path.home() / ".docker"), "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            env=minimal_env(), capture_output=True, check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RunnerError("Cannot discover Docker; start the local Docker engine") from error
    endpoint = result.stdout.decode().strip()
    if not endpoint.startswith("unix:///") or any(ord(char) < 32 for char in endpoint):
        raise RunnerError("Only a local Unix-socket Docker endpoint is supported")
    return endpoint


def mount_argument(source: Path, target: str) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow([
        "type=bind", f"source={source}", f"target={target}", "readonly", "bind-recursive=disabled",
    ])
    return buffer.getvalue()


def create_arguments(request: ExecutionRequest, image: str, name: str, workspace: Path) -> list[str]:
    limits = request.limits
    flags = request.command[1:] if request.command[0] == "pytest" else request.command[3:]
    launcher = "mutation_inventory.py" if request.mode == "inventory" else "run_pytest.py"
    arguments = request.mutation_paths if request.mode == "inventory" else [request.mode, json.dumps(flags), *["/tests/" + path for path in request.test_paths]]
    return [
        "create", "--pull=never", "--name", name, "--label", "io.specguard.runner.job=true",
        "--user", "65532:65532", "--network", "none", "--ipc", "none", "--cgroupns", "private",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
        "--cpus", str(limits.cpus), "--memory", f"{limits.memory_mb}m", "--memory-swap", f"{limits.memory_mb}m",
        "--pids-limit", str(limits.pids), "--ulimit", f"fsize={limits.file_size_mb * 1024 * 1024}:{limits.file_size_mb * 1024 * 1024}",
        "--ulimit", "core=0:0", "--ulimit", "nofile=128:128",
        "--tmpfs", f"/scratch:rw,noexec,nosuid,nodev,size={limits.scratch_mb}m,mode=1777",
        "--mount", mount_argument(workspace / "source", "/target"),
        "--mount", mount_argument(workspace / "tests", "/tests"),
        "--workdir", "/scratch", "--log-driver", "none", "--restart", "no", "--stop-timeout", "0",
        "--env", "TMPDIR=/scratch", "--env", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONUNBUFFERED=1",
        "--entrypoint", "/usr/bin/timeout", image,
        "--signal=TERM", "--kill-after=1s", f"{request.timeout_seconds}s",
        "/usr/local/bin/python", "-I", "-B", "-u", "/opt/specguard/" + launcher,
        *arguments,
    ]


def classify(state: dict, timed_out: bool, *, elapsed_seconds: float = 0, timeout_seconds: int = 0) -> tuple[str, str | None]:
    if state.get("OOMKilled"):
        return "resource_limit", "Container exceeded its memory limit"
    if timed_out:
        return "timeout", "Host execution deadline exceeded"
    if state.get("Status") != "exited" or state.get("Error"):
        return "infrastructure_error", "Container did not exit normally through the runner"
    code = state.get("ExitCode")
    # GNU timeout itself receives SIGKILL when an uncooperative child survives
    # its TERM deadline. Docker then reports 137 instead of timeout's usual 124.
    if code == 137 and timeout_seconds > 0 and elapsed_seconds >= timeout_seconds:
        return "timeout", "Container was killed after the execution deadline"
    if code == 0:
        return "passed", None
    if code == 124:
        return "timeout", "Container execution deadline exceeded"
    if code == 153:
        return "resource_limit", "Process terminated by the file-size limit"
    if code in {2, 5}:
        return "collection_error", "pytest collection failed, was interrupted, or found no tests"
    if code in {3, 4, 125, 126, 127} or not isinstance(code, int):
        return "infrastructure_error", "pytest/runner could not execute the requested suite"
    return "failed", "Test failure or interpreter/process termination"


class DockerRunner:
    def __init__(self, image_digest: str, *, interrupt_check=None, job_id=None):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
            raise ValueError("runner image must be a full immutable local image ID (sha256:...)")
        self.image_digest = image_digest
        if job_id is not None and not re.fullmatch(r'[0-9a-f-]{36}', job_id):
            raise ValueError('Invalid job identity')
        self.job_id = job_id
        self.interrupt_check = interrupt_check

    def checkpoint(self):
        reason = self.interrupt_check() if self.interrupt_check else None
        if reason:
            raise EvaluationStopped(reason)

    def _control(self, client: list[str], *args: str, timeout: int = 10) -> bytes:
        try:
            response = subprocess.run(
                [*client, *args], env=minimal_env(), capture_output=True, check=True, timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RunnerError(f"Docker {args[0]} failed or timed out") from error
        return response.stdout

    def _runtime(self, client: list[str]) -> dict[str, str]:
        info = self._control(client, "info", "--format", "{{json .SecurityOptions}}|{{.CgroupVersion}}|{{.OSType}}|{{.ServerVersion}}").decode().strip()
        security, cgroups, os_type, version = info.split("|")
        if os_type != "linux" or cgroups != "2" or "name=seccomp,profile=builtin" not in json.loads(security):
            raise RunnerError("Runner requires Linux, cgroups v2, and Docker's built-in seccomp profile")
        image = json.loads(self._control(client, "image", "inspect", self.image_digest, "--format", "{{json .}}"))
        labels = image["Config"].get("Labels") or {}
        if image["Id"] != self.image_digest or labels.get("io.specguard.runner.protocol") != "1":
            raise RunnerError("Image is not a supported pinned SpecGuard runner")
        if image["Config"].get("Volumes"):
            raise RunnerError("Runner image must not declare writable volumes")
        # The reviewed Dockerfile has no proxy credentials or arbitrary environment.
        allowed = {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"}
        if any(value.split("=", 1)[0] not in allowed for value in image["Config"].get("Env", [])):
            raise RunnerError("Runner image contains unexpected environment variables")
        return {"docker": version, "platform": image["Os"] + "/" + image["Architecture"],
                "python": labels["io.specguard.runner.python"], "pytest": labels["io.specguard.runner.pytest"],
                "mutmut": labels.get("io.specguard.runner.mutmut", "unavailable")}

    def _attach(self, client: list[str], name: str, timeout: int, output: OutputBuffer) -> bool:
        process = subprocess.Popen([*client, "start", "--attach", name], env=minimal_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + timeout + 2  # Container timeout plus kill/attach grace.
        timed_out = False
        try:
            with selectors.DefaultSelector() as selector:
                for stream in ("stdout", "stderr"):
                    selector.register(getattr(process, stream), selectors.EVENT_READ, stream)
                while selector.get_map() or process.poll() is None:
                    self.checkpoint()
                    if time.monotonic() >= deadline:
                        timed_out = True
                        break
                    for key, _ in selector.select(timeout=0.05):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if data:
                            output.add(key.data, data)
                        else:
                            selector.unregister(key.fileobj)
            if timed_out:
                self._control(client, "kill", name, timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()
        return timed_out

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        self.checkpoint()
        started = time.monotonic()
        name = "specguard-run-" + uuid.uuid4().hex
        output = OutputBuffer(request.limits.output_kb * 1024)
        status, error = "infrastructure_error", None
        state, runtime = {}, {}
        cleanup = True
        image = None
        with tempfile.TemporaryDirectory(prefix="specguard-exec-") as directory:
            workspace = Path(directory).resolve()
            client = None
            create_attempted = False
            try:
                stage_selection(request.target_snapshot, request.source_paths, workspace / "source")
                stage_selection(request.test_workspace, request.test_paths, workspace / "tests")
                config = workspace / "docker-config"
                config.mkdir(mode=0o700)
                client = ["docker", "--config", str(config), "--host", local_endpoint()]
                runtime = self._runtime(client)
                image = self.image_digest
                create_attempted = True
                arguments = create_arguments(request, image, name, workspace)
                if self.job_id:
                    arguments[1:1] = ['--label', 'io.specguard.evaluation.run=' + self.job_id]
                self._control(client, *arguments)
                self.checkpoint()
                execution_started = time.monotonic()
                timed_out = self._attach(client, name, request.timeout_seconds, output)
                execution_seconds = time.monotonic() - execution_started
                state = json.loads(self._control(client, "inspect", name, "--format", "{{json .State}}"))
                status, error = classify(state, timed_out, elapsed_seconds=execution_seconds, timeout_seconds=request.timeout_seconds)
            except (OSError, ValueError, KeyError, RunnerError, subprocess.SubprocessError) as exception:
                error = sanitize(str(exception).encode())[:1024]
            finally:
                if create_attempted:
                    try:
                        self._control(client, "rm", "--force", name)
                    except RunnerError:
                        # A failed create may never have allocated a container.
                        # Confirm absence rather than interpreting every rm error
                        # as a leaked job; daemon errors still fail closed.
                        try:
                            remaining = self._control(client, "container", "ls", "--all", "--filter", f"name=^/{name}$", "--format", "{{.ID}}")
                            cleanup = not remaining.strip()
                        except RunnerError:
                            cleanup = False
                        if not cleanup:
                            status = "infrastructure_error"
                            error = "Container cleanup could not be confirmed; remove owned container " + name
        return ExecutionResult(
            status=status, exit_code=state.get("ExitCode"), duration_seconds=round(time.monotonic() - started, 3),
            stdout=output.text("stdout"), stderr=output.text("stderr"), output_truncated=output.truncated,
            output_bytes_seen=output.seen, image_digest=image, container_name=name,
            oom_killed=bool(state.get("OOMKilled")), cleanup_succeeded=cleanup, error_message=error, runtime=runtime,
        )
