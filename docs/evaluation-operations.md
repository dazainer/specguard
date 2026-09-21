# Evaluation operations

The supported deployment is one private host, one SQLite database and one trusted worker. No Redis or separate database service is needed. The API only queues curated fixture evaluations; the CLI remains the reference execution path. Read the [README](../README.md) for the Compose quick start.

## Setup and configuration

Docker Desktop or a local Linux engine must support cgroups v2, default seccomp and the runner resource controls. The runner image is built separately with `docker build -t specguard-runner:evaluation docker/runner`; resolve its full `sha256:` image ID and set `EVALUATION_RUNNER_IMAGE`. Rebuild it if missing locally. Do not substitute a mutable tag.

Set `SPECGUARD_WORKSPACE` to the absolute repository root and create `.specguard-data/tmp` and `benchmark-runs` before `docker compose up --build -d`. The migration service must succeed before API/worker startup. The frontend binds localhost:8080 and API localhost:8000; override with `SPECGUARD_WEB_PORT` and `SPECGUARD_API_PORT` if occupied. The frontend proxies `/api` internally; its API Docs link defaults to localhost:8000 for the normal setup.

The worker mounts the Docker socket and stages inputs under a path mounted identically on the daemon host. `TMPDIR` in Compose is that absolute path. Do not use a remote Docker daemon or move staging to a container-only directory. Only the worker receives the socket. Application containers are trusted; test execution happens in separate restricted runner containers. On Linux, root-owned bind-mount files may require matching administrative permissions for host maintenance.

Compose databases live in the shared `evaluation-data` Docker volume (`/data/evaluations.db` and `/data/manual.db`); raw artifacts live in the host `benchmark-runs/web/`. SQLite WAL/shared-memory files stay on the Linux volume rather than a Docker Desktop host bind mount. Native development defaults put the evaluation DB under `backend/.specguard-data/`; use explicit paths when switching modes. Do not point two independently managed workers at the same data.

For native development, install backend requirements and frontend npm dependencies as in the README. From `backend/`, copy `../.env.example` to `.env`, set `EVALUATION_RUNNER_IMAGE`, then run:

```bash
.venv/bin/python -m app.evaluation.migrate
.venv/bin/python -m uvicorn app.main:app --reload
```

In a second terminal, from `backend/` with the same settings:

```bash
.venv/bin/python -m app.evaluation.worker
```

In a third terminal, from `frontend/`, use `npm run dev` and open localhost:5173. No API key is needed for evaluations. Legacy manual QA generation uses `OPENAI_API_KEY` when explicitly configured. The Compose environment deliberately leaves it empty.

## Migration and rollback

Evaluation schema changes use `backend/evaluation_migrations/` and Alembic revision `0001_evaluations`. `python -m app.evaluation.migrate` is explicit and repeatable; API startup never creates the evaluation schema. The legacy manual QA DB still uses its separate development `create_all` flow.

Before a future schema upgrade: stop submissions and the worker, back up the database and artifacts together, apply the migration, then start the matching application version and verify readiness. The initial migration's downgrade drops evaluation tables: it is destructive and is not a routine rollback strategy. Restore the backup with the matching code version instead. Never downgrade a live database or delete the DB to fix readiness.

## Health, progress and metrics

- `/api/health`: API liveness, independent of evaluation worker availability.
- `/api/evaluations/ready`: migrated database, worker heartbeat less than 30 seconds old, and immutable image configuration. It does not attest Docker health or image availability; execution performs those checks.
- `python -m app.evaluation.worker --health`: database and worker heartbeat check; used by Compose.
- `/api/evaluations/metrics`: run states, failure reasons, average queue time, stage-duration counts/totals/means and indexed mutant outcome counts. Mutant-detail counts shrink after retention; retained run reports hold the original summaries.
- Run detail: ordered persisted stage events, per-stage timings, cancellation state, failure reason and report. Supervisor stdout emits JSON with run ID and stage; inspect `docker compose logs worker`.

Execution JSON retains bounded stdout/stderr and resource/timeout classifications. Product views remove terminal control sequences, mask configured API keys and common credential patterns, and cap output. Pattern scrubbing is best-effort; private raw artifacts must still be protected. Never paste raw logs or context files into public issues without review.

## Cancellation, failure and recovery

Submission keys are globally idempotent for matching requests; reuse with different options returns 409. At most 100 runs can be queued. Runs execute serially, with a default 900-second ceiling (API permits 10–3600 seconds). Cancelled queued runs never start. Active cancellation interrupts the evaluator, cleans up exact run-labelled containers and retains partial observations. A cancellation arriving at the terminal write is resolved atomically.

API restarts do not stop evaluations. Gracefully stopping the worker interrupts its active run, records a failure, and releases its lease. Abrupt worker loss leaves a recoverable active record. Wait at least 30 seconds after the last heartbeat, then restart the worker; it fences the previous child, removes only containers carrying that run's label, and marks the record `failed / worker_lost`. The run is not automatically retried: submit a new key for an explicit retry. An OS process lock prevents two live supervisors from running against the same local DB, and a per-job lock prevents recovery from racing an old artifact writer.

If Docker cleanup cannot be confirmed, the failure reason ends in `cleanup_unconfirmed`. Restore Docker connectivity and inspect the exact run label:

```bash
docker ps -a --filter 'label=io.specguard.evaluation.run=RUN_UUID'
```

Only after confirming ownership should an operator remove the listed containers. Do not run broad `docker system prune` as a recovery step. If a child never releases its lock, recovery fails visibly rather than publish over a live writer; inspect the old process/container before restarting. Hard host/runtime failure can leave private staging directories; remove stale staging only with the worker stopped and no runner containers active.

## Retention and storage

Defaults: `EVALUATION_RETENTION_DAYS=7`, `EVALUATION_STORAGE_MB=1024` aggregate terminal artifact budget, `EVALUATION_RUN_STORAGE_MB=128` active-run budget. Set these environment variables for native development; add explicit environment overrides to the Compose worker service to change its defaults. The supervisor samples active output usage every 0.5 seconds; it is a cancellation threshold with bounded overshoot, not a filesystem quota. Per-container output/tmpfs/resource limits also apply.

After jobs and on idle loops, the worker removes expired or oldest terminal artifact directories until under budget. Queued/active artifacts are protected. Reports, timestamps, events and artifact metadata remain in SQLite; detailed mutant rows are removed. Expired logs/artifact/rendered-report endpoints return 410; JSON summaries remain available. The UI identifies expired data and offers retained JSON only. Never treat a missing raw artifact as a new measurement.

For a one-off retention pass, stop the worker first, then run `python -m app.evaluation.worker --prune` with the same paths/settings. Retained DB summaries and metadata accumulate; monitor DB size separately. SQLite can reuse freed pages; reclaim disk using `VACUUM` only during maintenance after backup. There is no automatic deletion policy for retained summary records.

## Consistent backup and restore

1. Stop API, frontend and worker (`docker compose stop frontend api worker`); wait for graceful worker shutdown and confirm no active runner containers. Disable any native worker using the same data.
2. Archive the `evaluation-data` named volume and `benchmark-runs/` together into a private backup. For example, with services stopped, `docker compose run --rm --no-deps -T api tar -C /data -cf - . > evaluation-data.tar` archives the volume; separately archive the host artifact directory. Include SQLite `-wal`/`-shm` sidecars if present; copying only a live `.db` file is unsafe. For native mode use its configured DB/artifact paths instead. Keep the matching source revision, manifest bundles and runner image ID with the backup; `docker image save` can archive the local runner for offline restore.
3. Restart with `docker compose up -d`. On restore, keep services stopped, restore the volume (for example, `docker compose run --rm --no-deps -T api tar -C /data -xf - < evaluation-data.tar` into an empty destination volume) and matching artifact directory/permissions, load/rebuild the matching runner, apply compatible migrations, then start and verify readiness and a retained report.

Backups include source context and generated code; use restricted permissions and your normal encrypted backup storage. `docker compose down` stops/removes application containers but retains the named database volume and bind-mounted artifacts. Never use `down -v` unless intentionally deleting database records. Remove verification data only when intentionally discarding its reports.

## Repository metadata

Suggested description: **Executable pytest evaluation from specifications, with isolated baselines and fair native-versus-generated mutation comparisons.** Suggested topics: `pytest`, `mutation-testing`, `test-generation`, `fastapi`, `react`, `docker`, `evaluation`. These are documented for repository owners; this implementation does not publish changes or mutate GitHub metadata.
