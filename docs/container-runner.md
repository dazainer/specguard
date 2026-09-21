# Local container runner

Phase 2 collects or executes one prepared Python suite inside Docker and returns a structured result. It supports the first standard-library-only benchmark and pinned pytest dependencies. The [integrated CLI](evaluation-cli.md) adds generation, repeated baseline gates and mutation comparison; the [product worker](evaluation-operations.md) exposes curated fixture runs.

## Build and prepare

Install the backend dependencies using the root README. Start Docker Desktop, or a local Linux Docker engine with a Unix socket, cgroups v2, and the built-in seccomp profile. The Docker CLI/engine must support `--mount ... bind-recursive=disabled`. Remote Docker endpoints are rejected. Build from the repository root:

```bash
docker build --tag specguard-runner:phase2 docker/runner
export SPECGUARD_RUNNER_IMAGE="$(docker image inspect specguard-runner:phase2 --format '{{.Id}}')"
cd backend
.venv/bin/python -m app.evaluation.prepare \
  ../benchmarks/subjects/first_subject/specguard.yaml \
  --fixture ../benchmarks/subjects/first_subject/generation-fixture.json \
  --output /tmp/specguard-first-subject-run
```

Preparation requires a new output directory. Use another path if that example already exists. The build downloads a digest-pinned Python base and hash-checked, pinned wheels; builds need network access on a cold cache. Execution never pulls an image or installs packages, and the test container has no external network. No API key is required.

Resolve the local image ID with `docker image inspect`; the runner rejects mutable tags. A multi-platform base digest, a built image's ID, and its platform config digest can differ. Record the actual local ID returned by Docker, rather than copying a digest from build output. Rebuilding may change the ID, including because of build attestations.

## Collect and run

From `backend/`, in the same shell:

```bash
.venv/bin/python -m app.evaluation.execute /tmp/specguard-first-subject-run \
  --image "$SPECGUARD_RUNNER_IMAGE" --suite native --collect-only
.venv/bin/python -m app.evaluation.execute /tmp/specguard-first-subject-run \
  --image "$SPECGUARD_RUNNER_IMAGE" --suite native
.venv/bin/python -m app.evaluation.execute /tmp/specguard-first-subject-run \
  --image "$SPECGUARD_RUNNER_IMAGE" --suite generated --collect-only
.venv/bin/python -m app.evaluation.execute /tmp/specguard-first-subject-run \
  --image "$SPECGUARD_RUNNER_IMAGE" --suite generated \
  --output /tmp/specguard-generated-result.json
```

`--output` must name a new file with an existing parent; otherwise JSON goes to stdout. Exit status is 0 for `passed`, 1 for an unsuccessful execution result, and 2 for CLI/setup validation errors. Collection imports test modules, so it receives the same isolation and limits as execution. Do not invoke pytest on prepared artifacts on the host.

Results include status, exit code, elapsed duration, capped stdout/stderr, truncation and observed byte count, immutable image ID, runtime versions, OOM flag, cleanup outcome, and the job's unique container name. Statuses distinguish `passed`, `failed`, `collection_error`, `timeout`, `resource_limit`, and `infrastructure_error`. Duration includes staging, Docker operations, and cleanup. The configured timeout applies to the test process; a host watchdog allows two additional seconds for kill escalation/attachment, and Docker control operations have separate finite deadlines.

The existing `report.json` stays `prepared`. Execution JSON is separate evidence; the integrated evaluator connects generation and baseline observations to its evaluation report. The `generated` example is a handwritten fixture, not evidence of AI quality.

## Execution boundary

`ExecutionRequest` accepts two input roots, explicit source/test selections, a constrained pytest argument list, collect/run mode, and typed resource limits. The CLI selects source files from the union of manifest context and mutation paths. Additional runtime source dependencies must therefore be declared within the reviewed selection. Native and generated suites are selected independently.

Each job copies at most 256 regular files / 4 MiB per source or test workspace. Symlinks, hardlinks, special files, traversal, sensitive paths, and overlapping selections are rejected. Only these copies are mounted, read-only, at `/target` and `/tests`; the original prepared directory is never mounted wholesale. Inputs are trusted curated directories that must not change concurrently during preparation/staging.

Containers run as UID/GID 65532 with a read-only root, no external network or shared IPC, all capabilities dropped, no-new-privileges, default seccomp, and explicit CPU/memory/no-extra-swap/PID limits. `/scratch` is a bounded tmpfs with file-size and open-file limits. Docker log persistence is disabled; the host drains stdout/stderr with one combined byte budget and removes terminal control sequences. Native conftest/config discovery and plugin autoload are disabled. Arbitrary dependency installation, host mounts, environment variables, and shell commands are not request options.

The manifest controls limits within schema bounds. Defaults are 1 CPU, 1024 MiB memory, 128 PIDs, 128 MiB scratch, 16 MiB per file, and 1024 KiB combined output. The manifest's test timeout overrides the typed request's 30-second default. Resource errors caught by test code can appear as ordinary test results; `resource_limit` requires OOM state or a file-size termination code. A non-OOM SIGKILL after the deadline is classified as timeout, including GNU timeout's kill escalation; arbitrary Python can still spoof process outcomes. See the [threat model](threat-model.md) for the limits of these observations.

The host client discovers the local socket, then uses an empty private Docker configuration and minimal environment. Tests receive neither host environment variables nor the Docker socket. Every completed/failed job attempts force-removal of its unique container and deletion of temporary staged inputs. If removal fails, the runner checks whether that exact container still exists; uncertain cleanup is an infrastructure error.

If a runner/daemon crashes abruptly, inspect the specific container name reported by the job and remove it with `docker rm --force <exact-container-name>`. The label `io.specguard.runner.job=true` can help identify owned jobs. Do not broadly delete containers: another evaluation may be active. After abnormal host termination, private `specguard-exec-*` staging directories may also need removal once their job is confirmed stopped.

## Verify locally

From `backend/`, with the image ID exported as above:

```bash
.venv/bin/python -m pytest -q
SPECGUARD_DOCKER_TESTS=1 .venv/bin/python -m pytest tests/evaluation/test_execution_docker.py -q
```

Normal tests do not require Docker and skip the opt-in tests. The Docker suite exercises normal/failing/crashing tests, collection and execution hangs, ignored termination signals, memory/PID/file/scratch limits, privilege and network controls, secret exclusion, output flooding, cleanup, and independent benchmark suites. Payloads are stored as `.txt` and only executed inside the runner. Set `SPECGUARD_DOCKER_RESULTS` to a local directory to retain individual fixture result JSON.

The CI workflow has a separate Docker build/verification job with no application secrets. Local measured results are in [Phase 2 validation](phase-2-validation.md). This runner is for local/private curated evaluation; ordinary container isolation is not a perfect security boundary or approval for a public multi-tenant execution service.
