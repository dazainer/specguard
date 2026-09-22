# Test SpecGuard yourself

Use the fixture UI first: it costs nothing, exercises real containers and makes expected results easy to check. Live AI evaluation is a separate CLI workflow; the web UI deliberately remains fixture-only.

## Start a persistent local setup

From the repository root, with Docker Desktop running:

```bash
docker build -t specguard-runner:evaluation docker/runner
export EVALUATION_RUNNER_IMAGE="$(docker image inspect specguard-runner:evaluation --format '{{.Id}}')"
export SPECGUARD_WORKSPACE="$PWD"
mkdir -p .specguard-data/tmp benchmark-runs
docker compose up --build -d
```

Open **http://localhost:8080**. Keep these exports in the terminal where you run Compose commands. Databases live in a named Docker volume; artifacts live in `benchmark-runs/web`. No temporary Claude scratch directory or OpenAI key is needed. `docker compose down` stops the stack without deleting its data; do not add `-v` unless you intend to delete the database.

For an existing native API on port 8001, start the frontend from `frontend/` with:

```bash
SPECGUARD_API_PROXY=http://127.0.0.1:8001 \
VITE_API_DOCS_URL=http://localhost:8001/docs npm run dev -- --host 127.0.0.1
```

Then open **http://127.0.0.1:5173**. The normal native API uses 8000; omit those overrides for it. Native setup details are in [operations](evaluation-operations.md). Frontend tooling requires Node 22.12+ (or supported Node 24/26).

## A concrete acceptance exercise

1. Select **shipping** under Curated subject and click **Register target**. It should become the selected target.
2. Choose **Baseline check**, then **Start baseline check**. Expect completed collection, two passing baseline repeats per suite, and no mutation score. Shipping has **8 native tests and 3 fixture tests**.
3. Choose the same target and **Mutation comparison**. Expect **13 mutants**, native **12/13 (92.3%)**, generated fixture **3/13 (23.1%)**, with excluded outcome categories visible. Timing depends on Docker/host load.
4. Open the result, toggle **Only where suites disagree**, switch between Native and Generated fixture, and expand a mutant. Inspect the literal Python diff and runner output.
5. Open a generated artifact: source should appear as text with its hash and baseline status. Expand collection and repeated-baseline logs. Download JSON, Markdown and CSV; check that the displayed denominator matches the exports.
6. Run **first_subject** for a larger example: **52 mutants**, **30 native tests / 7 fixture tests**, native **40/52**, fixture **29/52**. This is useful for paging through mutants.
7. Start another mutation comparison and click **Cancel run** while it is active. Expect a retained cancelled run with partial observations, not a successful comparison. Cancellation cannot undo a run that has already completed.
8. Refresh the page and reopen an older run. State must persist. To test API independence on disposable data, run `docker compose restart api` during mutation; the worker should continue.

These exact expected scores apply to the pinned handwritten fixtures, not to live AI output. A differing score warrants checking the subject commit, image and inventory hashes before interpreting it as a regression.

## Visual and keyboard checks

At 375, 768 and 1440 pixels wide, check the overview, completed comparison, cancelled result, code viewer and expanded mutant. Page content must fit; code/diff panes may scroll internally. Use DevTools device mode for widths.

Press Tab from the address bar: **Skip to content** should be first. Press Enter to reach the main content. Continue with Tab/Shift+Tab, use arrows on radio groups and Space on checkboxes, and Enter on mutant summaries. Focus must remain visible. In DevTools Rendering, emulate `prefers-reduced-motion: reduce`; animations/transitions should stop or become effectively immediate.

## Repeatable automated checks

From `frontend/`:

```bash
npm ci
npm test
npm run build
npx playwright install chromium
# Requires the running stack plus one completed, unpruned mutation comparison:
SPECGUARD_UI_URL=http://localhost:8080 npm run test:browser
```

The browser audit reads actual API records, checks all three widths, runs axe accessibility scans, tests keyboard interaction/reduced motion/exports, and saves screenshots plus `audit.json` under ignored `benchmark-runs/ui-audit/`. It also scans failed/cancelled records when available; it does not fabricate them or start paid calls. Automated accessibility checks complement manual inspection, not replace it.

From `backend/`, use `.venv/bin/python -m pytest -q`. See the [CLI guide](evaluation-cli.md) for Docker integration tests; live AI trials use a separately budgeted CLI workflow.
