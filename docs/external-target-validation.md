# External module validation

Two selected modules from **one** external repository, boltons 25.0.0, are available under `benchmarks/external/`. The unchanged source/native tests, BSD-3-Clause notices, upstream commit and per-file hashes are retained. Local bundle commits identify deterministic subsets, not whole upstream checkouts. Specs and handwritten fixtures are integration inputs authored by SpecGuard.

## Final offline fixture verification

| Subject | Native tests | Fixture tests | Inventory | Native killed / scorable | Fixture killed / scorable | Native / fixture errors |
| --- | --- | --- | --- | --- | --- | --- |
| boltons_mathutils | 11 | 3 | 113 | 88/110 (80.0%) | 58/110 (52.7%) | 3 / 3 |
| boltons_typeutils | 3 | 3 | 25 | 3/20 (15.0%) | 8/25 (32.0%) | 5 / 0 |

Both runs completed with two passing original-code baselines per suite and equal native/generated inventory/configuration hashes. Mutation import/collection errors remain excluded from the denominator; native and generated scorable denominators can therefore differ even with the same inventory. These fixtures are deliberately small and do not establish whole-module correctness or model quality.

The first math fixture incorrectly assumed Python-style negative indexing for `Bits`. Boltons 25.0.0 does not implement that behavior, so both baseline repetitions failed. That failed attempt is retained in `initial-attempts.json`; the fixture was explicitly corrected to a nonnegative index and rerun in a new output directory. Upstream source and native tests were never edited. The other initial module run completed. This is fixture integration/debugging, not a cherry-picked live-model experiment.

[Checked-in final results](../benchmarks/results/external-offline/results.json), [initial attempts](../benchmarks/results/external-offline/initial-attempts.json), and [environment](../benchmarks/results/external-offline/environment.json) record the evidence. Raw private runs are in ignored `benchmark-runs/external-fixture-20260922/` and `benchmark-runs/external-fixture-v2-20260922/`.

Normal tests verify upstream file hashes, safe preparation and native-test exclusion from model context. The subset rebuild script reproduced both pinned bundle commits. All target/native/generated code execution occurred inside the existing immutable Docker runner. No paid model calls were made for these external targets.
