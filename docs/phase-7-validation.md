# Phase 7 audit and validation

Reviewed 2026-09-22, separately from the Phase 0–6 checkpoint `930a81e`.

The UI preserves the evaluator API and metric semantics while adding reusable stage, outcome, suite, mutant and evidence components; labelled baseline eligibility; suite disagreements joined by mutant ID; provenance; responsive tables; keyboard focus/skip navigation; reduced-motion support; and frontend tests. Screenshots in `docs/ui/` show actual fixture runs. Frontend test JSON was captured from the real shipping evaluation, not fabricated model evidence.

## Findings fixed before commit

- Remount run detail when the route ID changes so prior-run results/source cannot appear under a new run URL. Fence asynchronous target lookups.
- Fence artifact requests on new selection, close, route change, unmount and retention changes; a delayed response cannot reopen stale source.
- Reset mutant state when its run/availability changes and provide a retry action after loading errors.
- Replace a space-containing suite heading ID so its accessible name resolves correctly.
- Remove the missing Vite template favicon reference.
- Update vulnerable build/test/browser/router packages. The final npm audit reports **zero known vulnerabilities**. Node 22.12+ is required; CI and Compose use Node 22. Major tooling/router updates were validated with tests, build and real browser workflows.

## Verification

- `npm test`: **22 tests passed**, including a regression test for delayed artifact responses after retention.
- `npm run build`: passed with Vite 8.3.0, Vitest 5.0.1 and React Router 7.18.4.
- `npm run test:browser`: **12 real-data viewport/accessibility checks passed**: overview, completed, failed and cancelled pages at **375/768/1440 px**; zero axe findings in the enabled WCAG A/AA rules on scanned states. Expanded mutant and execution log content was included.
- Browser checks also passed skip-link focus, visible focus, keyboard disagreement filtering/expansion, reduced motion, all three report downloads, no page-level JavaScript errors and no document overflow.
- Reviewed mobile comparison and desktop overview captures visually. Machine audit evidence is under ignored `benchmark-runs/ui-audit/`; the reusable script is `frontend/scripts/audit-ui.mjs`.
- Reviewed the full changed code/configuration and intentional fixture/screenshot files. No runtime database, environment file, build directory or node_modules is included in this commit.

Automated scans do not establish full accessibility conformance. Recent-run tables expose up to the API's latest 50 records; long-term benchmark trend charts and paginated history remain a product limitation. No rendering optimization claim is made without profiling. The web workflow remains fixture-only; live AI results are produced and labelled separately by the CLI.

Use [the test guide](testing-guide.md) for a persistent setup and an acceptance exercise with known expected results.
