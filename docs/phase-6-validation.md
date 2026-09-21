# Phase 6 validation — durable local evaluator

Phase 6 implementation is complete for the authorized **offline, curated, single-host** product scope. The evaluation API/UI uses the same report schema and evaluation pipeline as the CLI. No live model calls, benchmark-source exports, commits, pushes or deployments were made. GitHub repository metadata was not changed; proposed description/topics are in [operations](evaluation-operations.md).

## Implemented

- Explicit Alembic migration for a separate SQLite evaluation database: targets, durable/idempotent jobs, ordered events, artifacts, mutants and worker lease.
- Single worker supervising an evaluator subprocess, independent of API lifecycle; ownership checks, OS supervisor lock and per-job artifact lock; cancellation, runtime/storage thresholds, recovery and exact-label container cleanup.
- Consistent terminal reports, including late cancellation and interrupted JSONL observations. Cleanup failures remain visible rather than becoming successful cancellations.
- Curated fixture-only API and React pages: registration, submission, polling, cancellation, source/log inspection, native/generated comparison, filtered/paginated mutants and JSON/Markdown/CSV exports.
- Readiness, structured run/stage logs, queue/failure/outcome metrics and stage-duration aggregates; bounded private artifacts, scrubbed product views and retention with preserved JSON summaries.
- Compose migration/API/worker/frontend stack, with SQLite on a shared Linux Docker volume and private host artifact/staging directories. No unnecessary Redis/database service.
- Updated README, measured benchmark table, architecture diagram, real browser screenshots, demo, operations/backup guide and current methodology/CLI links.

## Verification

| Check | Result |
| --- | --- |
| Full backend suite | **328 passed, 27 skipped** (Docker checks are separately opt-in) |
| Docker isolation, evaluator and product suites | **27 passed**, 191.68 seconds |
| Final worker regression | All **4 product Docker tests passed** again after structured-log changes (21.02 seconds) |
| Product unit/API coverage | **14 passed**, including migration, idempotency, ownership, cancellation race, supervisor spawn error, cleanup error, process locking, retention and partial JSONL recovery |
| Dependency consistency | `pip check`: no broken requirements |
| Frontend | TypeScript/Vite production build passed, both native and Compose builds |
| Compose | Built and ran migrations, API, worker and nginx frontend; health and readiness checked |
| Actual API restart | Restarted API while the reservation evaluation was mutating; the same durable job completed with native **40/52**, fixture **29/52** |
| Actual abrupt worker loss | SIGKILL during mutation; waited 32 seconds for lease expiry; restarted worker; retained `failed / worker_lost` and no containers with the interrupted run label |
| Runtime/storage bounds | Opt-in Docker tests produced `failed / run_deadline` and `failed / artifact_limit` |
| CLI/API contract | Export parsed as `EvaluationReport`, matched the on-disk report and retained equal native/generated inventory hashes |
| Retention lifecycle | With worker stopped, zero-day pruning removed terminal raw data; open UI cleared previously displayed source, hid Markdown/CSV downloads, retained JSON, and logs returned 410; queued cancellation also verified |
| Chromium browser | Real registration, submission/cancellation, desktop/mobile layout, artifacts, logs, filtering/pagination and report downloads; failed and polling-error states |

Browser verification used temporary Playwright 1.51.1 / Chromium 134, desktop 1440×1080 and mobile 390×844. No page-level JavaScript errors occurred in the main workflow; document width matched the mobile viewport on landing and result pages. Screenshots in the README are real fixture run data, not fabricated measurements. Fixture generation is explicitly labelled and manual heuristic coverage remains separate.

Local environment: macOS ARM64 with Docker Desktop, Python 3.12 backend/application/runner, Node.js 22 frontend build. Runner ID for this verification:

```text
sha256:ec2b2941caf0c74f65c5b25ba5ef69a6e7995c9f41d61c350109632945264152
```

The ID is local, not a registry publication; rebuild and resolve your own ID. The final reservation verification job was `8a3c2925-a5e4-407a-b7c3-30cc59823d93`; abrupt-loss recovery job was `80063afb-a77b-4975-a398-200c0278d72c`. The isolated Compose stack was stopped after verification; its named database volume was retained. Private raw evidence and the completed run/API metrics snapshot were preserved under ignored `benchmark-runs/phase6-validation/` before retention testing. These identifiers document this local verification and are not portable seed data.

## Issue found and corrected

The initial Compose version placed SQLite WAL/shared-memory files on a macOS host bind mount. During the first API-restart exercise the worker exited with signal-derived code 135 (bus error, not reported as OOM), leaving a durable active record; the browser completion check consequently timed out. The filesystem interaction was suspected, not independently proven as the crash's root cause. Compose now places the shared SQLite DB on a Linux Docker volume. The repeated full API-restart evaluation, worker-loss recovery and browser checks passed with that configuration. Original bind-mount verification files were preserved, not silently presented as a successful run.

## Reproduce

Follow the [README](../README.md) for a fresh Compose start and [CLI guide](evaluation-cli.md) for the independent evaluator. From `backend/`, after building the runner and exporting its immutable ID:

```bash
.venv/bin/python -m pytest -q
SPECGUARD_DOCKER_TESTS=1 SPECGUARD_RUNNER_IMAGE="$EVALUATION_RUNNER_IMAGE" \
  .venv/bin/python -m pytest tests/evaluation/test_execution_docker.py \
  tests/evaluation/test_evaluation_docker.py tests/evaluation/test_product_docker.py -q
```

To check actual process boundaries, start a full web evaluation and use `docker compose restart api` while it is mutating. Confirm the same run completes. In a separate test run, kill only the test worker, wait for its 30-second lease to expire, restart it and inspect the retained failure and exact container label. Run destructive lifecycle exercises only on disposable verification data, not a user's active evaluation. The [operations guide](evaluation-operations.md) describes retention, backup and cleanup.

## Limits

No live prompt quality or external-repository generalization is claimed. CI was configured but not remotely executed in this session. Container isolation is not a tamper-proof or multi-tenant security boundary. Summary/event records remain in SQLite after raw retention and require capacity monitoring. Application transitive dependencies are not fully locked. Legacy manual QA still has its original in-process generation and development `create_all` lifecycle; evaluation durability/migration guarantees do not apply to it. Phase 7 UI optimization is separate future work.
