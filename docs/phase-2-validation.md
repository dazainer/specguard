# Phase 2 completion report

Phase 2 implements and locally verifies the container-isolated execution boundary. The threat model was written before the runner. Generated/test payloads were executed only inside Docker; no live model calls, mutation analysis, web execution endpoint, or database changes were added.

## Implemented behavior

- Typed `ExecutionRequest` / `ExecutionResult` contracts and a synchronous local `DockerRunner` support collection and execution, with separate statuses for success, test failure, collection error, timeout, resource limits, and infrastructure failure.
- A minimal Python image pins the base by multi-platform digest and all pytest dependencies by version and wheel hash. Runtime requests require a full immutable local image ID, validate the runner protocol/environment, and never pull images.
- Every job uses UID/GID 65532, network none, private namespaces, a read-only root and selected input mounts, dropped capabilities, no-new-privileges, default seccomp, bounded scratch, CPU/memory/no-extra-swap/PID/file/open-file limits, and container/host deadlines.
- Only bounded private copies of selected regular files are mounted. Symlinks, hardlinks, special files, sensitive paths (including mixed-case environment filenames), traversal, and collisions are rejected. Host environment, client proxy configuration, Git metadata, and Docker socket are excluded.
- Combined stdout/stderr is drained with a byte cap and sanitized; Docker log persistence is disabled. Container removal and staged-workspace deletion run on success and failure. Cleanup uncertainty overrides the result with an infrastructure error.
- Fixed pytest configuration, disabled conftest/plugin discovery, and separate source/test mounts keep native tests out of generated-suite execution.
- `python -m app.evaluation.execute` runs a selected prepared suite and prints or saves JSON without rewriting Phase 1's `prepared` report. A separate CI job builds the image and opts into the Docker checks.

## Local environment and pins

Verified on macOS with Docker Desktop's Linux ARM64 engine, Docker server **29.5.3**, cgroups **v2**, and built-in seccomp. The backend environment uses Python **3.12.13**; the frontend build uses Node **24.13.0**. Hosted CI is configured for Python 3.12 and Node 22, but has not run because these changes have not been pushed.

| Component | Verified pin |
| --- | --- |
| Python base | `python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2` |
| Local runner image ID | `sha256:57387c3c1ea5a0bf2603f193550a882df2307d484d4e7a55f1f340ce9844c0eb` |
| In-container Python / pytest | 3.12.13 / 8.3.0 |
| Other locked wheels | iniconfig 2.3.0, packaging 24.2, pluggy 1.6.0 |
| Benchmark revision | `aeb8c2ba30521204c17e9843141f8e118dc5bc21` |

The local image ID is provenance for this verification, not a published registry reference. Rebuild locally and resolve the new ID with `docker image inspect` as explained in the [runner guide](container-runner.md).

## Verification

| Check | Result |
| --- | --- |
| Full default backend suite | **271 passed, 14 skipped**; Docker checks deliberately opt in |
| Deterministic runner tests | **46 passed**, included in the full suite |
| Opt-in real Docker suite | **14 passed** |
| Backend dependency check | No broken requirements |
| Frontend production build | Passed |
| Documented CLI: native collect / run | **30 collected / 30 passed** |
| Documented CLI: handwritten generated fixture collect / run | **7 collected / 7 passed** |
| Whitespace check | `git diff --check` passed |

The Docker suite uses 128 MiB memory, 0.5 CPU, 32 PIDs, 16 MiB scratch, 1 MiB per-file limit and 16 KiB output for adversarial cases. Timeout fixtures use a two-second deadline. Benchmark runs use the typed defaults or manifest limits as appropriate.

| Fixture / observation | Measured result |
| --- | --- |
| Normal suite / collection | Passed; collection lists the test without running its body |
| Assertion failure | `failed`, exit 1 |
| Import/collection failure | `collection_error`, exit 2 |
| Infinite loop | `timeout`, exit 124; 2.420 seconds including lifecycle |
| Collection hang | `timeout`, exit 124; 2.561 seconds including lifecycle |
| Ignore SIGTERM | `timeout`, exit 137 after escalation; 3.499 seconds including lifecycle |
| Unbounded memory allocation | `resource_limit`, exit 137, Docker OOM flag true |
| Repeated subprocess/fork creation | Reached PID limit; fixture confirmed exhaustion and cleaned children |
| Interpreter crash | `failed`, exit 139; container removed |
| Output flood | 2,097,172 bytes observed; retained combined output at most 16 KiB, truncation true |
| Isolation fixture | Six checks passed: UID/capabilities/NNP/seccomp/cgroups; secret and host-asset exclusion; HTTP/DNS blocked; root/input writes rejected; per-file limit; scratch exhaustion |
| Native configuration contamination | Native pytest config and both native/generated conftest files did not execute in generated run |
| Cleanup | Every fixture reported success and its exact container name was confirmed absent from the daemon; staged copies removed |

Host-only deterministic tests cover traversal, unsafe command options, symlink/hardlink/FIFO/secret/oversized input rejection, byte caps even for invalid UTF-8, status classification, floating-image/remote-daemon rejection, host environment exclusion, and cleanup after create/attach/inspect failures. A failed create that never allocated a container is distinguished from an actual cleanup failure.

The first Docker verification exposed two issues, both corrected and rerun: GNU timeout's kill escalation produced exit 137 and needed deadline-aware classification; this Docker kernel also exposes dormant tunnel interfaces, so the network fixture now verifies that only loopback is active and that outbound HTTP/DNS calls fail. No isolation setting was weakened.

CLI result files and prepared inputs from this local verification were retained under `/private/tmp/specguard-phase2-cli-3uz0wjup`; individual adversarial results were retained under `/private/tmp/specguard-phase2-results`. These temporary paths are local evidence and may be removed by the operating system. Reproducible test sources and commands are in the repository.

## Files and decisions

- Added `backend/app/schemas/execution.py`, `backend/app/evaluation/execution_runner.py`, `execution_workspace.py`, `execution_output.py`, and `execute.py`.
- Added the pinned image, hash lock, fixed pytest configuration, and trusted launcher under `docker/runner/`.
- Added deterministic and opt-in Docker tests under `backend/tests/evaluation/`, and text-only adversarial payloads under `backend/tests/fixtures/runner/`; registered the Docker marker in `backend/pytest.ini`.
- Added the threat model, runner guide, and this validation report; updated the root README, benchmark README, v2 design, and CI workflow.
- Preserved existing Phase 0/1 work and the user's implementation plan. No commits, pushes, or deployments were performed.

This completes Phase 2's local acceptance criteria. Docker is **container-isolated execution**, not a perfect security boundary. Inputs, manifests, build inputs, host runner, and local daemon are trusted; hostile public multi-tenant execution is outside this scope. Tests establish observed controls on this local platform, not proof against kernel/runtime vulnerabilities. A non-OOM kill after the deadline is classified as timeout by timing inference; untrusted Python can spoof test output/exit codes. Resource errors caught by a test can appear as normal test outcomes. An abrupt host/daemon crash can leave stopped containers or staging files requiring cleanup.

The handwritten fixture establishes runner operation, not model quality. Phase 3 should connect executable generation to collection and repeated original-code baseline gates, retaining execution evidence in the evaluation report. Mutation analysis remains Phase 4.

Suggested commits: `feat: add pinned container execution runner`, `test: verify container isolation and benchmark execution`, and `docs: document local runner and phase 2 verification`.
