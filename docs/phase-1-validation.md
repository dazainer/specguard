# Phase 1 completion report

Phase 1 defines and verifies the v2 contracts and first offline benchmark. No Phase 2 runner, live generation, target-code execution, mutation engine, web endpoint, or database migration was introduced. The existing Phase 0 changes and the user's untracked implementation plan were preserved.

## Implemented behavior

- Strict version-1 manifests validate repository sources and full commit pins, Python/pytest scope, context visibility, paths, trusted command arrays, resource/artifact limits, and generation configuration. The YAML loader rejects duplicate keys, unsupported versions, non-UTF-8 input, aliases, tags, and oversized input.
- Filesystem checks reject absolute/traversing paths and symlinks. Snapshot export also rejects Git symlink/submodule/special entries, secret paths, case collisions, and excessive file counts/size.
- Executable output schemas and artifact validation enforce generated-directory boundaries, Python test filenames, syntax, file counts and byte limits, duplicate/overwrite protection, LF normalization, and SHA-256 hashes. Syntax is parsed as data; no generated module is imported or executed.
- Report schemas record generation configuration, provenance, artifacts, separate suite observations, baseline repeats, costs/tokens, and mutation outcomes. They reject inconsistent scores, failed/unstable baseline eligibility, incomparable mutant inventories/configurations, and measured-outcome claims in prepared reports.
- A first-party reservation-pricing subject is pinned at `aeb8c2ba30521204c17e9843141f8e118dc5bc21` in `target.bundle`. Its specification, public interface, native tests, readable source mirror, and handwritten output fixture are checked in as reviewable inputs. It has no third-party runtime dependencies.
- `python -m app.evaluation.prepare` exports the bundle and creates a new run directory containing canonical manifest/context JSON, optional fixture artifacts, and a `prepared` report. Failure leaves no partial run; existing output directories are refused.

## Decisions

The first experiment is spec-plus-code / white-box. Model context contains only the specification, public interface, and declared implementation module; native tests remain excluded. A separate spec-only contract is available but is not mixed into the first experiment.

The local Git bundle provides a real, reproducible standalone benchmark commit without inventing a remote revision or fetching floating dependencies. Its rebuild script writes only a temporary Git object database and the fixture bundle; it does not commit to SpecGuard's repository. The exported target contains no Git metadata.

Artifact and run data are kept in the filesystem/JSON contract. Manual QA endpoints, schemas, UI behavior, and persistence remain unchanged by Phase 1. PyYAML 6.0.3 is now an explicit dependency for the manifest loader; it was already installed transitively in the local environment.

## Verification

| Command/check | Result |
| --- | --- |
| `cd backend && .venv/bin/python -m pytest -q` | **225 passed**, including all 93 Phase 0 tests; warnings treated as errors |
| `cd backend && .venv/bin/python -m pip check` | No broken requirements |
| `cd frontend && npm run build` | Passed |
| Preparation CLI run twice with the subject manifest and handwritten fixture | Both prepared successfully; matching provenance and artifact hashes |
| Rebuild the bundle in a temporary subject copy | Reproduced the exact pinned commit |
| Export Pydantic JSON schemas for manifest, generated output, and report | Passed |
| `git diff --check` | Passed |

Preparation tests also verify that the readable mirror matches the exported pinned tree, native tests do not enter model context, outputs round-trip through strict schemas, invalid inputs leave no partial output, and malicious-looking Python passed as artifact text is never executed. Snapshot adversarial fixtures cover symlinks, submodules, `.git`, `.env`, traversal, and absolute paths.

All checks ran locally on macOS with Python 3.12.13, Node 24.13.0 and Git 2.52.0. Normal backend tests use deterministic fixtures and block outbound sockets. No live model calls, benchmark pytest collection, or native/generated benchmark execution occurred. Hosted CI has not run because these changes have not been pushed.

## Files changed in Phase 1

- Added `backend/app/evaluation/__init__.py`, `paths.py`, `manifest.py`, `context_builder.py`, `artifact_validator.py`, `snapshot.py`, and `prepare.py`.
- Added `backend/app/schemas/evaluation.py`.
- Updated `backend/requirements.txt` to pin PyYAML explicitly.
- Added `backend/tests/evaluation/__init__.py`, `conftest.py`, `test_manifest.py`, `test_artifacts.py`, `test_prepare.py`, and `test_report.py`.
- Added the first subject's `specguard.yaml`, `spec.md`, `interface.md`, `generation-fixture.json`, `target.bundle`, `rebuild_bundle.py`, and `README.md` under `benchmarks/subjects/first_subject/`.
- Added its readable target mirror: `target/src/__init__.py`, `target/src/reservations.py`, `target/tests/test_native.py`, `target/requirements.lock`, and `target/LICENSE`.
- Added `docs/v2-design.md`, `docs/evaluation-methodology.md`, and this report; updated the root `README.md` with preparation instructions and the new dependency.

## Limitations and next phase

- Prepared artifacts are not executable-evaluation evidence. Their report deliberately leaves execution, image digest, mutation, and model-usage measurements unpopulated.
- The handwritten output fixture is not a model-quality benchmark. Native and generated subject suites await execution inside the Phase 2 runner.
- Subjects and manifest commands are trusted curated configuration. Host Git parsing and filesystem preflight are not security boundaries for hostile concurrent users or arbitrary public repository uploads.
- Remote repository fetching is unsupported even though HTTPS repository declarations can be validated.
- Exact runner image, Python patch version, pytest dependencies, and adversarial runtime controls must be pinned and verified in Phase 2. No ordinary Docker runtime is described as a fully secure sandbox.
- Docker's client is installed locally, but its daemon was not running when checked. Start Docker Desktop before Phase 2 runtime verification.
- No repository commits, pushes, portfolio/resume edits, or deployments were performed. Only the intended uncommitted work and prior user changes remain; the working tree is not claimed to be clean.

The recommended next phase is **Phase 2: threat model and container-isolated execution runner**, with normal and adversarial fixtures verified before live model output is connected.

Suggested commits:

1. `feat: define evaluation manifest artifact and report contracts`
2. `feat: add pinned offline benchmark preparation`
3. `docs: define v2 design and evaluation methodology`
