# Executable evaluation CLI

Phase 3 adds executable generation, collection and repeated original-code baselines. Phase 4 adds a pinned mutmut inventory and independent native/generated mutation comparisons. The manual QA application remains separate.

From the repository root, with Docker running:

```bash
docker build --tag specguard-runner:evaluation docker/runner
export SPECGUARD_RUNNER_IMAGE="$(docker image inspect specguard-runner:evaluation --format '{{.Id}}')"
cd backend
.venv/bin/python -m app.evaluation.evaluate \
  ../benchmarks/subjects/first_subject/specguard.yaml \
  --image "$SPECGUARD_RUNNER_IMAGE" \
  --output ../benchmark-runs/first-baseline --baseline-only
```

Use a new output directory. The default provider is the subject's handwritten fixture; it makes no API calls. Omit `--baseline-only` to include the full mutation comparison. Test and target code execute only in the container runner. Neither generated nor native pytest artifacts should be executed on the host.

The run directory retains canonical manifest/context, exact prompt and version, validated generated files and hashes, content-free generation attempt logs, collection/baseline execution JSON, timing data, and report/Markdown/CSV summaries. Invalid generation receives at most three attempts with bounded backoff. Terminal provider errors stop immediately. Generated suites with failing, skipped, empty, timed-out, or inconsistent baselines are ineligible for mutation; collected artifacts from rejected suites move to `quarantine/`. Every collected case must pass every configured baseline repetition.

Two prompt configurations are available through `--strategy contract-v1` and `--strategy boundary-v1`; `--context spec_only` withholds implementation files from the prompt. The fixture provider returns the same handwritten response regardless of prompt, so fixture comparisons cannot measure prompt quality.

`--live --model gpt-4o-mini` selects the OpenAI adapter using backend configuration. It sends the declared benchmark context to OpenAI and incurs API usage. This path is covered by a mocked transport test, but **no live calls were made during this implementation**, per the user's instruction to keep verification offline. JSON-mode responses still undergo local schema, artifact, collection and baseline checks. See the [official Chat Completions reference](https://developers.openai.com/api/reference/resources/chat) for API behavior.

## Mutation adapter

The image pins **mutmut 2.4.4**, its dependencies, and build tools with hashes. Its existing `Context`, `list_mutations` and `mutate` APIs produce the inventory inside Docker; SpecGuard does not implement mutation operators. This deliberately uses the version-2 source-variant API rather than mutmut's CLI scheduler. The adapter runs each variant in a fresh resource-limited container through the already-verified runner. Mutmut's CLI parallelization, relevant-test selection and incremental database are not used.

The same sorted, hashed inventory and mutation configuration are used for both suites. Records retain stable IDs, mutmut node/operator names, file/line/diff, execution result, elapsed duration, a failing test when observed, and an initially `unreviewed` manual-review field. Syntax-invalid mutants are separate; timeout, error and suspicious observations do not count as kills. Score is `killed / (killed + survived)` with the denominator displayed. Raw inventory execution and per-mutant JSONL logs are retained. Inventory size is capped at 1000 mutants; exceeding the cap fails rather than silently sampling.

The whole-suite baseline gate runs before mutation or cache reuse. `--cache-dir ../.specguard-cache` optionally reuses native mutation results keyed by source/test content, commit, image, inventory and configuration. Cache provenance identifies the original run and duration. Generated mutations always rerun; timeouts/errors/suspicious cached results are not reused. Three measured cold/warm pairs averaged 77.103 s / 43.225 s on the reservation subject; see [Phase 5 evidence](phase-5-validation.md) for the environment and limits.

## Five-subject offline benchmark

```bash
.venv/bin/python -m app.evaluation.benchmark \
  --subjects ../benchmarks/subjects \
  --image "$SPECGUARD_RUNNER_IMAGE" \
  --output ../benchmark-runs/five-subjects
```

This runs five first-party, MIT-licensed synthetic subjects: reservation pricing, pagination, shipping charges, access policy and interval overlap. Each includes a specification, interface, pinned Git bundle, dependency lock, native suite and handwritten fixture. These are five benchmark subjects, not five independent external repositories.

The benchmark writes `results.json`, `results.csv`, `summary.md`, `aggregates.json`, `environment.json`, `failures.json`, and each run's raw evidence. Failed runs remain in the attempted denominator. `--trials 2 --strategies contract-v1 boundary-v1` exercises repeated configurations; population score variance is null when fewer than two eligible scores exist. Fixture variance is not model nondeterminism. The two-strategy, two-trial matrix completed 20/20 runs locally; see [Phase 5 evidence](phase-5-validation.md).

`benchmark-runs/` and `.specguard-cache/` are ignored by Git because they contain potentially large/private run artifacts. Keep them if you need raw measurements. The product wraps this same evaluator in a durable worker; see [operations](evaluation-operations.md) and [Phase 6 validation](phase-6-validation.md).

## Tests

From `backend/`:

```bash
.venv/bin/python -m pytest -q
SPECGUARD_DOCKER_TESTS=1 .venv/bin/python -m pytest \
  tests/evaluation/test_execution_docker.py \
  tests/evaluation/test_evaluation_docker.py \
  tests/evaluation/test_product_docker.py -q
```

CI uses deterministic providers and no model calls. Docker tests cover full fixture evaluation on all five subjects and rejection of invalid baseline behavior. See the [threat model](threat-model.md): Docker isolation and observed exit/test counts are not tamper-proof proof against malicious Python or a kernel/runtime exploit.
