# Container runner threat model — Phase 2

Written before implementing the runner. This boundary supports local/private evaluation of curated Python targets. It is **container-isolated execution**, not a fully secure sandbox and not a public multi-tenant arbitrary-code service.

## Trust and protected assets

Treat test and target Python as untrusted once execution begins. Trust the reviewed benchmark manifest, pinned runner image/build inputs, host runner process, Docker CLI/daemon, and host kernel (or Docker Desktop's Linux VM). Host credentials, environment variables, user files, Git metadata, Docker socket, host/internal networks, other jobs, and host CPU/memory/disk/process/log capacity must not be exposed to tests.

The host Docker client necessarily controls a privileged local daemon. Only a local Unix socket endpoint is supported; the socket is used by the host client and is never mounted into the container. Runtime Docker commands use a private empty client configuration and a minimal process environment so Docker's user-configured proxy variables cannot be injected into tests. Image downloads/dependency installation happen only during the explicit trusted build, never during execution.

## Threats and controls

| Attack/failure | Control and verification |
| --- | --- |
| Infinite loop, collection hang, ignored signals | Container PID 1 timeout wrapper with kill escalation, plus host wall-clock watchdog and force removal; exercise test and collection hangs |
| Memory exhaustion | Explicit memory limit and equal memory+swap limit (no extra swap); distinguish Docker's OOM flag from ordinary failures |
| Process/fork bomb | Private PID namespace, explicit PID limit, no restart, container removal; exercise exhaustion inside a small test container |
| Excessive CPU | Explicit CPU quota; verify cgroup control from inside container |
| File/disk exhaustion | Read-only root and input mounts, bounded scratch tmpfs, RLIMIT_FSIZE/core/nofile bounds, no writable host bind; exercise file and scratch limits |
| Output flooding | Disable Docker log storage; drain stdout/stderr continuously with a combined byte cap, sanitize control sequences, retain only capped text |
| Outbound HTTP/DNS or host-service access | `--network none`, no published ports or host namespace; exercise connect and DNS attempts |
| Reading secrets or broad host paths | Copy only explicit source/test selections; reject symlinks, hardlinks, special files, sensitive directories and oversized snapshots; mount only private copies |
| Path traversal/symlink escapes | Reuse Phase 1 path validation and validate every staged entry; container writes cannot reach original host inputs |
| Elevated privileges, dangerous syscalls | Numeric non-root UID/GID, drop all capabilities, no-new-privileges, retained default seccomp profile; verify effective UID/caps/seccomp/NNP |
| Docker socket, devices, host /proc | No socket/device/host PID mounts; private namespaces, Docker's proc masking, no privileged mode; verify socket absence and read-only kernel settings |
| Subprocesses | Permitted only inside the same resource-limited container; no claim to prohibit all subprocess execution |
| Interpreter crash, collection/test failure | Structured statuses preserve exit code, capped output, OOM/timeout evidence and cleanup outcome |
| Native tests contaminating generated evaluation | Stage source and selected suite separately; fixed pytest config, disabled plugin autoload/conftest/cache, explicit test paths, no discovery of target-native tests |

Use argument arrays throughout; no shell interpretation. Do not accept arbitrary Docker options, mounts, container environment, shell commands, or floating runtime images through the execution request. Enforce limits before starting any test, including adversarial verification fixtures.

## Workspace and lifecycle

Inputs come from private, trusted prepared directories and must not be modified concurrently by hostile host processes. Validate and copy the selected files into a fresh private directory, bounded to 256 files / 4 MiB for each of source and test selections. The container sees only the copied source and selected tests, read-only. Its mounts never expose repository `.git`, the user's home, the full application checkout, host secrets, or host-writable scratch. Container scratch is a bounded tmpfs and disappears when the container is removed.

Create a uniquely named/labeled container, attach to bounded output streams, inspect its state, then force-remove it in a finally block. Destroy staged copies after retaining the structured result. A cleanup failure is an infrastructure failure and includes the owned container name for operator cleanup. Never remove containers by a broad name/pattern. The in-container timeout also limits jobs if the host runner process dies; an abrupt host/daemon failure can still leave stopped containers/staging directories requiring operator cleanup.

## Residual risks and limits

- Docker shares a kernel with its Linux host/VM. Kernel, daemon, runtime, or image vulnerabilities can defeat ordinary container isolation. A public hostile multi-tenant service requires separate review and likely a stronger runtime boundary.
- This does not defend against a malicious host user, a compromised Docker daemon, host filesystem races, or sensitive content deliberately embedded in reviewed target files. Inputs/configuration are curated and private.
- tmpfs uses memory and can interact with host/VM swap policy; host disk encryption/swap policy is an operator responsibility. Container memory+swap settings are not an assurance about VM-wide memory handling.
- Untrusted Python can spoof pytest output or exit codes. Process results and schema validation establish operational behavior, not tamper-proof proof of test quality. Baseline/mutation methodology and later review remain necessary.
- Core isolation is enforced by Docker, not by import filtering or Python AST checks. `noexec` scratch does not stop Python from interpreting text stored there.
- Resource-limit classification is conservative: report OOM or a file-size termination when supported by exit/state evidence; a caught allocation/PID/file error may appear as an ordinary test result. Never infer an OOM solely from a test's printed message.
- GNU timeout's forced kill returns 137; a non-OOM kill observed after the deadline is classified as timeout. This timing inference cannot distinguish every deliberate signal/exit spoof by hostile Python. Docker's OOM evidence takes precedence.
- The initial runner supports the standard-library-only benchmark and the image's pinned pytest dependencies. Arbitrary package installation and native conftest/plugin loading are intentionally unsupported.

## Sources

- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) — CPU, memory and equal memory/swap behavior.
- [Docker default seccomp profile](https://docs.docker.com/engine/security/seccomp/) — retain the built-in protection; do not use `seccomp=unconfined`.
- [Docker none network driver](https://docs.docker.com/engine/network/drivers/none/) — network namespace without external networking.
- [Docker tmpfs mounts](https://docs.docker.com/engine/storage/tmpfs/) — bounded temporary writable storage and swap caveat.

Actual verification results and deviations are recorded in [Phase 2 validation](phase-2-validation.md).

## Phase 3–4 extension

Executable generation remains a host-side provider operation over explicitly declared context; it is separate from test execution. The new baseline gate consumes bounded structured pytest observations. Those observations can be spoofed by malicious Python in the same process and do not strengthen the security boundary described above.

The mutation inventory launcher runs pinned mutmut inside the same resource-limited container and treats source as data. The host validates its bounded JSON inventory, stages one source variant at a time, and runs each suite in a fresh container with the existing controls. No mutation/test code runs on the host, and no writable host mount is added. Optional native-result caches are trusted local artifacts, keyed by complete execution inputs; they never bypass repeated baseline gates. Raw run artifacts and exact prompts may contain private benchmark content and belong in ignored/private output directories.

## Durable product boundary

The evaluation API accepts only installed curated subjects and fixture providers. It persists work in a separately migrated SQLite database; one trusted worker supervises evaluator children. Only that worker receives the Docker socket. An OS lock prevents concurrent supervisors; owner checks, parent-loss checks, per-job locks and exact container labels fence interrupted work. API restarts preserve runs; worker loss retains a failed record after cleanup. Cancellation and runtime/storage limits retain partial observations without promoting them to successful results.

Product log views are bounded and scrubbed, while raw artifacts remain private. Retention removes terminal raw artifacts while preserving summary reports. The app has no authentication and binds localhost in Compose: it is not a public execution service. Read [operations](evaluation-operations.md) for backups, cleanup failures and recovery limitations. The legacy manual QA workflow has separate, weaker task durability and is not covered by the evaluation worker guarantees.
