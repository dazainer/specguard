# Phase 0 stabilization report

Phase 0 is implemented and verified locally. Hosted GitHub Actions verification remains pending a push; no commit or push was performed. The existing untracked `SpecGuard_V2_Implementation_Plan.md` was preserved unchanged.

## Baseline and results

The original backend had 23 passing tests, a pytest-asyncio configuration warning, and a collection warning caused by importing `TestGenerationResult` under a test-like name. The frontend build failed on the unused `Github` and `BarChart3` imports.

| Verification | Result |
| --- | --- |
| Existing environment: `cd backend && .venv/bin/python -m pytest -q` | 93 passed; warnings treated as errors |
| Existing environment: `cd frontend && npm run build` | Passed |
| Fresh temporary environment: Python 3.12 venv and `python -m pip install -r requirements.txt` | Passed |
| Fresh environment: `python -m pytest -q` | 93 passed; no warnings |
| Fresh environment: `python -m pip check` | No broken requirements |
| Fresh frontend: `npm ci --no-audit --no-fund (isolated temporary cache)` | Installed all 72 locked packages |
| Fresh frontend: `VITE_API_DOCS_URL=https://docs.specguard.invalid/custom npm run build` | Passed; custom URL verified in bundle and localhost docs URL absent |
| Fresh backend: `python -m uvicorn app.main:app --host 127.0.0.1 --port 18765` | Startup, health, API docs, project create/delete, sample document upload, and statistics passed |
| `git diff --check` | Passed |

Fresh setup used an isolated temporary copy with no existing virtualenv, node_modules, database, or developer `.env`. Python was 3.12.13 and Node was 24.13.0 on macOS. CI is configured for Python 3.12 and Node 22 on Ubuntu; that hosted environment has not yet been exercised. Network downloads and the temporary localhost smoke server needed execution outside the tool sandbox. The smoke server was stopped afterward. No live AI calls were made.

Verification produced no unexpected untracked repository artifacts. The working tree contains the intended uncommitted changes and the user's existing implementation plan; it is deliberately not reported as clean.

## Behavior and architectural decisions

- Preserve the existing manual QA workflow and API endpoints.
- Keep `requirements.txt` with pinned direct dependencies. Remove unused `python-docx`, `markdown-it-py`, and unconfigured `alembic`; defer packaging migration and migration infrastructure.
- Give malformed JSON, empty responses, and schema validation failures the same bounded retry path. Retry provider connection errors and HTTP 408/409/429/5xx responses, while other provider errors terminate. Disable nested SDK retries so the configured retry count controls the total attempts.
- Avoid echoing model content or provider payloads in retry logs. Validation statistics still describe first-pass successes, successes after retry, and failures within one process.
- Preserve successful tests when individual requirements fail, record covered/failed requirement counts in suite metadata, and fail runs that generate no tests.
- Roll back failed generation transactions before persisting the failed suite status. This also preserves previously stored requirements when regeneration fails.
- Preserve zero-valued scores in project statistics and Markdown exports.
- Use temporary SQLite databases with foreign-key enforcement, scripted AI fakes, and blocked outbound socket connections in tests. No new test dependencies were required.
- Configure pytest explicitly and treat warnings as errors; fix the collection warning with an import alias rather than suppression.
- Keep the local API Docs default, with a public build-time `VITE_API_DOCS_URL` override.

## Files changed

| Area | Files |
| --- | --- |
| Frontend | `frontend/src/App.tsx`, `frontend/src/pages/ProjectPage.tsx`, `frontend/src/vite-env.d.ts` |
| Backend fixes | `backend/app/services/ai_client.py`, `backend/app/services/pipeline.py`, `backend/app/routes/projects.py`, `backend/app/routes/test_suites.py` |
| Test configuration and dependencies | `backend/pytest.ini`, `backend/requirements.txt`, `backend/tests/conftest.py` |
| Regression coverage | `backend/tests/test_schemas.py`, `backend/tests/test_ai_client.py`, `backend/tests/test_file_parser.py`, `backend/tests/test_pipeline.py`, `backend/tests/test_routes.py` |
| CI and repository housekeeping | `.github/workflows/ci.yml`, `.gitignore`, `.env.example` |
| Documentation and licensing | `README.md`, `LICENSE`, `docs/phase-0-validation.md` |

## Deferred work and next phase

- Hosted CI is pending; local verification does not establish an Ubuntu/Node 22 CI result.
- Backend transitive dependencies are not locked. This phase verifies current fresh installation, not indefinitely identical dependency resolution.
- Background tasks and validation statistics remain process-local. Durable execution and migrations belong to the later productization phase.
- Successful regeneration replaces document requirements; older suites retain test cases but lose links to the replaced requirements. Historical requirement versioning needs a later data-model decision.
- The score remains a structural heuristic. Executable test generation, container isolation, mutation evaluation, and frontend end-to-end coverage have not been added.

The recommended next phase is Phase 1: define the versioned manifest and report contracts, document evaluation methodology, and introduce one pinned benchmark subject. Phase 1 has not started.

Suggested commits, if approved:

1. `fix: restore frontend build and configure API docs link`
2. `test: stabilize generation and add API pipeline regression coverage`
3. `ci: validate backend tests and frontend production build`
4. `docs: repair setup screenshots and MIT licensing`
