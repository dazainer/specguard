# SpecGuard v2 contracts

SpecGuard turns specifications into executable pytest suites, requires those suites to pass against original code in a container, and compares their mutation results with native tests. The existing manual QA API and frontend remain independent.

The preparation command implements contracts and offline preparation only. It does not invoke an AI provider, install target dependencies, import target modules, collect pytest tests, or execute generated artifacts. A prepared report is not an evaluation result.

Phase 2 adds the separate [container runner](container-runner.md), typed execution requests/results, and an execution CLI. Preparation retains the Phase 1 behavior described here; execution results are separate JSON documents when using the standalone execution command. The integrated evaluator now records baseline and mutation evidence in its shared report. The [durable product worker](evaluation-operations.md) calls the same evaluator.

## First vertical slice

The first subject is the first-party reservation-pricing module in `benchmarks/subjects/first_subject/`. It has two public functions, deterministic integer arithmetic, validation and boundary behavior, no runtime dependencies, and an MIT license. Its native tests and implementation are pinned together in a local Git bundle. This makes preparation possible offline without inventing a remote commit or depending on a moving branch.

The experiment is **spec-plus-code / white-box**. Model-visible input consists of `spec.md`, `interface.md`, and the explicitly declared `src/reservations.py`. The native test directory, other repository files, and the deterministic generated-test fixture are excluded from context. A separate `spec_only` mode is supported by the contract and requires an empty source-file list; it must be labeled separately in results.

The handwritten `generation-fixture.json` exercises artifact validation and preparation. Its provider/model identifiers explicitly identify it as a fixture. It is not evidence of model quality, and Phase 1 does not execute it.

## Modules and boundaries

| Module | Responsibility |
| --- | --- |
| `app/evaluation/manifest.py` | Strict versioned manifest, YAML loader, context/command/resource policies |
| `app/evaluation/paths.py` | Portable relative paths, containment, symlink rejection |
| `app/evaluation/snapshot.py` | Export the pinned Git tree from a local bundle without a checkout or hooks |
| `app/evaluation/context_builder.py` | Read only declared context files, normalize text, hash canonical context |
| `app/evaluation/artifact_validator.py` | Validate generated paths, counts, byte sizes, syntax, and content hashes |
| `app/evaluation/prepare.py` | Prepare a new run directory with a JSON report; no execution |
| `app/schemas/evaluation.py` | Executable generation, provenance, baseline, mutation, and report contracts |
| `app/schemas/execution.py` | Strict runner request and structured execution result |
| `app/evaluation/execution_runner.py` | Container lifecycle, resource controls, bounded capture, classification and cleanup |
| `app/evaluation/execution_workspace.py` | Bounded private copies of explicitly selected source/test inputs |
| `app/evaluation/execute.py` | Collect or run one prepared suite inside Docker |

Preparation uses the host Git executable only to process the curated bundle as data. Git receives argument arrays, an isolated configuration, a temporary object database, no credential helpers, and no checkout hooks. Symlinks, submodules, special entries, sensitive paths, and case-colliding files are rejected. The exported snapshot contains no `.git` directory. The readable `target/` mirror is maintained for review; preparation trusts the pinned bundle, not uncommitted edits to that mirror.

This is validation of trusted benchmark inputs, not isolation for hostile repositories. Bounds apply to manifest/context/artifact/export sizes, but Git itself is not sandboxed against a malicious object database. Arbitrary public uploads and network repository fetching are outside Phase 1.

## Manifest version 1

The canonical example is `benchmarks/subjects/first_subject/specguard.yaml`. `Manifest` rejects unknown fields, coercion of numeric strings/booleans into limits, unsupported schema versions, and unsupported languages. YAML duplicate keys, custom tags, anchors, and aliases are rejected. Manifest input is limited to 64 KiB.

| Section | Contract |
| --- | --- |
| `schema_version`, `language` | Integer `1`, string `python` |
| `repository` | Full lowercase 40-character commit SHA; exactly one of a relative `.bundle` path or credential-free HTTPS `.git` URL |
| `specification` | Specification path relative to the subject directory |
| `environment` | Python `3.12`, a dependency-lock path inside the pinned target, optional trusted install argv |
| `context` | Explicit mode, interface path relative to the subject directory, selected Python files relative to the target |
| `tests` | Separate native paths and generated directory, pytest command argv, wall timeout, 2–10 baseline repeats |
| `mutation` | Explicit target/excluded paths and mutation timeout |
| `limits` | Bounded memory, CPUs, PIDs, output, scratch space, and file size; enforcement belongs to Phase 2 |
| `artifacts` | Generated file-count, per-file byte, and total-byte bounds |
| `generation` | Provider, model identifier, prompt version, temperature, optional seed |

All paths use normalized relative POSIX syntax, without leading/trailing slashes, empty components, `.` or `..`, drive letters, backslashes, encoded escapes, or control characters. `.git`, `.env`, and `.env.*` components are prohibited. File resolution rejects every symlink component, including symlinks that happen to point inside the root. Native, generated, and mutation/context source paths must be separate. Paths are interpreted in their documented roots, not against the shell's current directory.

Manifests are trusted configuration reviewed with each curated subject. Commands are argument arrays, never shell strings. Supported executable names are `python`, `python3`, `pytest`, and `uv`; this is not a sandbox for commands. The baseline command specifically invokes pytest and may contain only `-q`, `-v`, `--strict-markers`, or `--strict-config`. The runner will append exactly one suite's paths; manifests cannot smuggle native tests into a generated run through baseline arguments. No command is executed during preparation.

Remote HTTPS URLs are validated for a future fetch boundary, but preparation rejects them explicitly. They are not fetched or claimed to be SSRF-safe. Local bundles must contain `refs/heads/main` and the pinned commit. Exports are limited to 256 files and 4 MiB of total contents; bundle input is limited to 4 MiB.

Path preflight assumes subject inputs are trusted and do not change concurrently. It does not claim to prevent filesystem races in attacker-controlled host directories. Phase 2 must stage reviewed inputs in a private workspace before mounting anything.

## Generation artifacts

`ExecutableTestGenerationResult` contains `files`, `assumptions`, and `targeted_requirements`; each file has `path` and `content`. The validator permits only `test_*.py` beneath the configured generated directory. It rejects duplicates (including case differences), overwrites, syntax errors, symlinks, and configured count/byte-limit violations. CRLF and CR line endings become LF before hashing. SHA-256 and UTF-8 byte length are recorded for every normalized file.

AST parsing is structural validation. It neither executes the module nor establishes that it is safe, collectible, correct, or comprehensive. Arbitrary Python with valid syntax can pass; execution belongs exclusively inside the future container runner.

## Prepared run directory

```text
run/
  manifest.json             # canonical validated manifest
  context.json              # exact model-visible context, without native tests
  report.json               # version 1, status=prepared
  target/                   # pinned source/native tests/dependency lock; no .git
  generated/                # optional, separate generated-test workspace
    .specguard/generated_tests/test_reservations.py
  generation-fixture.json   # optional original structured fixture
```

The output directory must be new. Work is staged in a private temporary directory and renamed after validation succeeds; failed preparation leaves no partial run. Existing outputs are refused. Inputs/output parents must not be concurrently modified by untrusted processes.

`report.json` records the target commit, hashes of the normalized manifest/specification/context and raw dependency lock, model/prompt configuration, artifact hashes, and preparation tool versions. Run IDs differ by design; the pinned snapshot, context, and artifact hashes repeat. The image digest, token usage, model cost, execution metrics, and mutation results remain null/unmeasured until those stages exist. The Python version is the requested target version, not a claim that an execution environment was instantiated.

The generated and native suites have separate report entries. Mutation summaries must have internally consistent outcome counts, denominator and score, stable successful baseline repeats, a runner image digest, and matching native/generated inventory/configuration hashes. These schema checks validate report consistency; only the future runner can establish evidence that the observations occurred.

## Next boundaries

Phase 2 provides the threat model and container-isolated runner, a pinned image and pytest dependencies, and normal/adversarial verification. Phase 3 connects a provider and baseline gate. Phase 4 integrates mutation tooling. The manual QA database is not expanded until the filesystem/JSON contract is proven. Docker execution is container-isolated execution, not a fully secure sandbox.
