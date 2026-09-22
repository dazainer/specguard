# Small external module targets

Two real module targets from **one** open-source repository: boltons 25.0.0, upstream commit `c23dbdadb6fecdf505eb4231559561913b84c13f`.

- `boltons_mathutils`: unchanged math helpers/Bits implementation and upstream math tests.
- `boltons_typeutils`: unchanged sentinel/type helpers and upstream type tests.

BSD-3-Clause notices are preserved. Each `upstream.json` records source/test hashes and provenance. Local bundle commits represent explicit file subsets plus a dependency lock; they are not mislabelled as upstream commits. No upstream code is imported on the host. Specs and small handwritten fixtures were authored for this integration from upstream documentation, so this is a selected-module evaluation, not a whole-project quality claim or an independent black-box specification study.

Run from `backend/` after building/resolving the runner image:

```bash
.venv/bin/python -m app.evaluation.benchmark \
  --subjects ../benchmarks/external --output ../benchmark-runs/external-new \
  --image "$EVALUATION_RUNNER_IMAGE"
```

This command uses **fixtures**, not AI. The default five-subject benchmark and web catalog remain synthetic-only. Results must be reported separately. These subjects add external relevance but must not be described as two independent repositories.

Rebuild the deterministic local subset bundles with `python3 benchmarks/external/rebuild_bundles.py` from the repository root. The script verifies upstream hashes before building and never imports target code.

See [validation results and limitations](../../docs/external-target-validation.md), including the initial failed fixture attempt.
