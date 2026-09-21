# First subject: reservation pricing

This first-party, MIT-licensed benchmark uses two deterministic functions: booking quotes and cancellation refunds. It exercises validation, inclusive range boundaries, guest fees, discount thresholds and order, integer rounding, and refund thresholds. These behaviors provide concrete candidates for later mutation analysis. It has no third-party runtime dependencies.

The first experiment is **spec-plus-code / white-box**. Context consists of `spec.md`, `interface.md`, and `src/reservations.py`; native tests are withheld. `generation-fixture.json` is a handwritten deterministic stand-in for model output, clearly labeled as such. It is not a model-generated suite or a benchmark result.

## Pin and files

- Source revision: `aeb8c2ba30521204c17e9843141f8e118dc5bc21`.
- `target.bundle`: offline Git bundle containing that revision and `refs/heads/main`.
- `target/`: readable mirror of the pinned source, native pytest suite, dependency lock, and MIT license.
- `specguard.yaml`: versioned manifest with paths, context, generation configuration, and runtime limits.
- `rebuild_bundle.py`: deterministically rebuilds the benchmark revision in a temporary Git object database. It never commits to the SpecGuard repository or executes target/test code.

The commit belongs to this standalone bundled benchmark, not to a published remote repository. Changing `target/` alone does not change evaluation inputs: rebuild the bundle and explicitly update the manifest pin for a new revision. Rebuilding unchanged files must print the same commit. Git bundle pack bytes need not be identical across Git versions; the pinned tree and commit are the identity.

## Prepare without Docker or an API key

From the SpecGuard repository root, with Git and the backend dependencies installed:

```bash
cd backend
.venv/bin/python -m app.evaluation.prepare \
  ../benchmarks/subjects/first_subject/specguard.yaml \
  --fixture ../benchmarks/subjects/first_subject/generation-fixture.json \
  --output /tmp/specguard-first-subject-run
```

The output path must not already exist. Choose a new path for another run. The command exports the pinned snapshot, builds model-visible context, validates and writes fixture artifacts, and saves `manifest.json`, `context.json`, and `report.json`. The report's status is `prepared`; execution/mutation fields remain unmeasured. No target dependencies are installed, no pytest collection occurs, and no benchmark/generated code is imported or executed.

Do not run the prepared pytest artifacts on the host. The [Phase 2 runner guide](../../../docs/container-runner.md) explains how to collect and execute each suite inside Docker. Live generation is Phase 3 work.

To rebuild the bundle from the readable mirror, from the repository root:

```bash
python3 benchmarks/subjects/first_subject/rebuild_bundle.py
```

Backend tests verify reproducible export, native-test exclusion from context, path/symlink rejection, artifact validation, report round-tripping and mutation eligibility. Opt-in Docker tests independently execute the benchmark's 30 native cases and 7 handwritten fixture cases; this verifies runner operation, not model quality or mutation effectiveness.
