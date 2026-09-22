# Phase 5 — offline benchmark completion

The authorized offline scope is complete. **20/20 evaluations passed** across five pinned, first-party synthetic subjects, two prompt configurations, and two trials per configuration. These are benchmark subjects, not independent external repositories. The fixture provider returns handwritten tests unchanged by the prompt: this verifies repeatable pipeline behavior, **not prompt effectiveness or live-model quality**. Live trials remain deliberately excluded by the user's instruction.

| Subject | Native killed / denominator | Fixture killed / denominator | Completed trials |
| --- | --- | --- | --- |
| access_policy | 7/7 (100.0%) | 6/7 (85.7%) | 4/4 |
| first_subject | 40/52 (76.9%) | 29/52 (55.8%) | 4/4 |
| intervals | 4/6 (66.7%) | 3/6 (50.0%) | 4/4 |
| pagination | 12/13 (92.3%) | 8/13 (61.5%) | 4/4 |
| shipping | 12/13 (92.3%) | 3/13 (23.1%) | 4/4 |

All trials used equivalent native/generated mutant inventories, repeated passing original-code baselines and the same pinned runner. The retained JSON/CSV includes collected counts, baseline pass rates, all outcome categories and explicit mutation-score denominators. Scores were identical across the four fixture trials per subject; reported population score variance is zero. Timing variance remains visible in aggregates.json. Failures remain part of attempted-run denominators; this matrix recorded none.

## Measured optimization

The earlier uncached profile attributed about 61 of 65 seconds to mutation execution. Optional native-result reuse was implemented in response. Three sequential cold/warm pairs on the reservation subject measured:

| Pair | Cold seconds | Warm seconds |
| --- | --- | --- |
| 1 | 68.707 | 37.715 |
| 2 | 81.451 | 48.601 |
| 3 | 81.152 | 43.360 |

Mean: **77.103 s cold**, **43.225 s warm**, a **1.78× ratio of means** for these local fixture runs. Every pair preserved inventory hashes and native/generated killed counts. Baselines and generated mutations reran; native observations were reused with their original run IDs. This is a local measurement, not a general production speedup claim. Runs were sequential with no competing evaluation containers, although ordinary editing/build activity and host/VM scheduling can affect wall time. Cold/warm order was fixed, not randomized.

## Reproduction and evidence

- [Checked-in results and CSV](../benchmarks/results/phase5-offline/results.csv), [machine-readable results](../benchmarks/results/phase5-offline/results.json), [environment](../benchmarks/results/phase5-offline/environment.json), [variance](../benchmarks/results/phase5-offline/aggregates.json), [failure taxonomy](../benchmarks/results/phase5-offline/failures.json).
- [Raw per-pair timing/cache evidence](../benchmarks/results/phase5-offline/performance.json) and [performance summary](../benchmarks/results/phase5-offline/performance-summary.json).
- Full local raw artifacts remain under `benchmark-runs/phase5-final/` (Git-ignored), including each collection/baseline result and per-mutant execution log. The original profiling run remains a private temporary directory if the OS has not removed it.
- The matrix environment records the evaluator implementation hash at invocation. Phase 6 edits happened later; future reproduction may therefore have a different implementation hash even with identical subject and image pins.

From the repository root build `docker build --tag specguard-runner:evaluation docker/runner`, then export `SPECGUARD_RUNNER_IMAGE="$(docker image inspect specguard-runner:evaluation --format '{{.Id}}')"`. From `backend/`:

```bash
.venv/bin/python -m app.evaluation.benchmark --subjects ../benchmarks/subjects \
  --image "$SPECGUARD_RUNNER_IMAGE" --output ../benchmark-runs/new-matrix \
  --trials 2 --strategies contract-v1 boundary-v1 --cache-dir ../.specguard-cache/new-matrix
```

For each cold/warm pair, invoke `app.evaluation.evaluate` on `first_subject/specguard.yaml` twice with separate new output directories and the same initially empty `--cache-dir`. Repeat with three different empty cache directories. Compare each run's `timings.json`, `native-cache.json`, `report.json`, and per-mutant logs. Do not run competing Docker jobs while profiling.

No live-model trials, external repository metric, deployment, commit or push is claimed. See [evaluation CLI](evaluation-cli.md) for commands and [methodology](evaluation-methodology.md) for eligibility and scoring rules.
