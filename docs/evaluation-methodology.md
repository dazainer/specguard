# Executable evaluation methodology — version 1

The preparation command produces inputs, not execution or mutation measurements. The evaluator and product worker subsequently collect tests, gate on repeated baselines and compare mutation results. A handwritten fixture must always be labeled `provider=fixture` and excluded from live-model quality claims.

## Experiment identity and context

Every run records its complete manifest, pinned source commit, specification/context/dependency-lock hashes, context mode, generation provider/model, prompt version, temperature, and seed when supported. Execution stages will also record the immutable runner image digest, Python patch version and dependency/tool versions actually used. A model seed does not guarantee determinism.

The initial benchmark is spec-plus-code: only the specification, public interface description, and manifest-selected implementation modules enter the model context. Native tests are withheld. Spec-only runs exclude implementation files and form a separate experimental group. No retrieval system or whole-repository context is used.

The first subject is a small first-party reservation-pricing implementation with no third-party runtime dependencies. Its snapshot is pinned with native tests in a local bundle and can be exported without network access. The manifest fixes Python 3.12; the runner fixes the container and hashed pytest dependencies before execution.

## Eligibility gates

The intended execution order is:

1. Validate the structured response, paths, file types, counts, byte sizes, and Python syntax.
2. Collect the generated suite inside the container, recording collection failures separately.
3. Run it against the unmodified pinned source with no native tests included.
4. Require a nonempty passing suite and at least the configured number of passing baseline repeats, with stable collected/passed counts. Timeouts, resource limits, test failures, infrastructure failures, and empty suites are ineligible.
5. Only then evaluate the accepted suite against mutants. Evaluate the native suite through the same collection/baseline gates independently.

Initially the acceptance unit is the whole suite. A failing or flaky generated suite is rejected; no silent selective removal of failing tests is permitted. Future per-test quarantine would require an explicit protocol change and reporting of all rejected tests. Skipped/xfail tests must not inflate accepted-test counts; the initial mutation report gate requires every collected test to pass.

Syntax checks are not execution or security checks. No generated Python, including the deterministic fixture, is run directly on the host.

## Fair native/generated comparison

Both suites use the same original source commit, runner image, dependency lock, resource limits, mutation configuration and mutant inventory. Run the suites separately; generated-suite execution must not discover or load native tests, native conftest files, or native pytest configuration implicitly. The runner must isolate discovery/configuration and supply the selected paths explicitly.

The report stores one source provenance record and requires equal inventory and configuration hashes for native/generated mutation comparisons. The pinned mutmut adapter records stable mutant identities and raw engine outputs. Preparation alone does not generate or score mutants.

## Metrics and denominators

| Metric | Definition |
| --- | --- |
| Generation success rate | Successful structured generation runs / all attempted generation runs; retries within a run do not add runs |
| Collection success rate | Successfully collected nonempty suites / suites submitted for collection; report generation failures separately |
| Baseline pass rate | Passing baseline repetitions / all recorded baseline repetitions; report run-level suite acceptance separately |
| Accepted/rejected tests | Collected test cases in accepted/rejected suites under the whole-suite policy; unknown collection counts remain null |
| Mutation score | `killed / (killed + survived)`; explicit denominator stored; zero denominator gives null |
| Mutation categories | Generated, killed, survived, timed out, invalid, errors, suspicious; categories partition the generated inventory |
| Runtime | Generation duration, individual baseline durations, and mutation duration in seconds; use monotonic clocks |
| Repeat variability | Baseline pass rate, per-repeat outcomes/counts, and population variance of repeat durations in seconds squared |
| Model usage/cost | Reported input/output tokens and estimated USD cost when available; absent data is null, not zero |

Timeouts, invalid mutants, errors, and suspicious outcomes are visible and are never silently counted as kills or survivors. Equivalent mutants are a known limitation; mutation score is evidence of sensitivity to the tested changes, not proof of correctness. Manual review of equivalent/questionable mutants belongs in the per-mutant artifacts once mutation integration exists.

`EvaluationReport` defines the per-run contract in `backend/app/schemas/evaluation.py`. It retains raw repeat outcomes, verifies reported pass rates and duration variance, and validates mutation arithmetic and baseline eligibility. Aggregate generation/collection rates are computed across run reports, with numerator and denominator stated explicitly. Live-model repeated trials will also report mutation-score variance across runs; preparation-only fixture runs are excluded.

The comparison table must show both suites' collected counts, baseline pass results, killed/survived/timeout/invalid/error/suspicious counts, mutation score, and denominator. A report must not replace failure categories with a single score.

## Reproduction and publication

Use the preparation command in the first subject's README. Retain the manifest, context, artifacts, hashes, and report; preserve failed runs as failures once execution exists. Model-dependent trials must be run explicitly outside normal CI. CI uses deterministic fixtures and performs no AI calls.

Only report measurements after collection, baseline and mutation stages have run in the documented environment. At least five pinned subjects must complete before making a multi-repository benchmark claim. Prepared artifacts, a passing contract test suite, and handwritten fixture tests alone do not meet that standard.
