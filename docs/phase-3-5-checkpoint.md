# Saved implementation checkpoint — Phases 3–5

Historical checkpoint. Phase 5's authorized offline work is now complete; see [Phase 5 validation](phase-5-validation.md) and the newer [Phase 6 checkpoint](phase-6-checkpoint.md).

Work paused at the user's request to conserve session usage. Files are saved in the working tree; no commits, pushes or deployments were performed. Prior Phase 0–2 work is preserved.

## Phase 3: implemented and verified offline

- Provider interface with deterministic fixture provider and adapter around the existing AI client's OpenAI transport; manual generation API unchanged.
- Separate versioned executable prompts, bounded retries, sanitized attempt metadata, validated artifacts, exact prompt/configuration retention and token observations when available.
- One-command CLI for generation, container-only collection, repeated original-code baselines, whole-suite acceptance/quarantine, and retained JSON/Markdown/CSV reports.
- Structured pytest observations reject missing/ambiguous counts, skipped tests, failures, timeouts and flaky/count-changing baselines before mutation.
- Deterministic unit tests cover retries, terminal errors, secret-safe logs, provider parameters, collection/baseline failures, quarantine and the shared evaluation pipeline.

The user explicitly selected **offline fixture verification**. Automatic approval review rejected the attempted live smoke-check command before execution; no live API call or source export occurred. The OpenAI adapter is mock-tested, not live-verified. This preference persists when resuming; do not initiate live trials without new explicit authorization.

## Phase 4: implemented, full fixture runs completed

- mutmut 2.4.4 generates variants inside the pinned image; all operators come from the existing engine.
- Both suites receive identical inventory/configuration hashes and fresh isolated execution per mutant. Stable ID/operator/location/diff, duration, observed failing test and manual-review placeholders are retained.
- Timeouts, invalid mutants, errors and suspicious results remain separate from kills. Scores require successful repeated original-code baselines and show their denominator.
- A fixed fixture captured from the real mutmut inventory tests parsing. Unit tests cover outcome normalization, exclusions and cache identity/integrity.
- First full run: 52 mutants; native killed 40/52 (76.92%); handwritten fixture killed 29/52 (55.77%). No timeout/invalid/error/suspicious outcomes occurred in that run.

Raw first-run evidence: `/private/tmp/specguard345-first-profile/`. All-five-subject evidence: `benchmark-runs/phase345-fixtures/` (Git-ignored). Every subject completed successfully. The first all-five run was an implementation verification run; its environment implementation hash was computed incorrectly from an empty file selection. That bug is fixed for subsequent runs. Do not use that initial hash as implementation provenance.

Verified image: `sha256:cfb3ab969cc2fd896294d53653c424842e2222e1861acbacd6019f8c7721e155`, locally tagged `specguard-runner:phase345`. Docker 29.5.3, Linux ARM64, Python 3.12.13, pytest 8.3.0, mutmut 2.4.4. Rebuild/resolve a fresh image ID if unavailable; the tag is not a published registry reference.

## Phase 5: progress saved, not complete

- Added four small first-party synthetic subjects to the existing reservation benchmark; all five have commit pins, offline bundles, specs, interfaces, native suites, handwritten fixtures and MIT licenses.
- Implemented the sequential benchmark matrix CLI, JSON/Markdown/CSV/environment exports, explicit failure taxonomy, trial aggregation and variance calculations.
- Implemented two prompt strategies. Offline fixtures deliberately return the same response for either strategy; they cannot establish model-quality differences.
- Profiled the first uncached run: total 65.319 s; native mutation 30.966 s; generated mutation 29.689 s. Mutation execution dominates this trace.
- Added optional native-result caching in response to that profile, including complete execution-input keys, provenance, integrity checks and refusal to reuse ambiguous results. Baselines always rerun.
- **Not completed:** repeated two-strategy matrix, warm-cache before/after timing, final checked-in benchmark summaries and README measurement table, full Phase 5 completion/limitations report. No speedup claim is warranted yet.

## Resume checklist

1. Read this checkpoint and `docs/evaluation-cli.md`; review the working tree rather than resetting prior uncommitted work.
2. Keep provider verification offline unless the user changes that instruction.
3. Finish reviewing Phase 4 adapter/cache/report edge cases. The adapter intentionally wraps mutmut's version-2 source-variant API, not its CLI scheduler; no custom mutation operators or worker pool were built.
4. Run the offline repeated matrix in a **new** output directory (`--trials 2 --strategies contract-v1 boundary-v1`). Label it deterministic pipeline evidence, not prompt-quality evidence.
5. Measure cold/warm native-cache performance sequentially without concurrent Docker workloads. Retain per-stage traces, original cache observations and variance; do not infer a general speedup from one noisy run.
6. Produce concise, checked-in benchmark summaries with provenance and links to reproduction commands. Keep large raw artifacts in ignored run directories. Clearly say five synthetic subjects, not five external repositories.
7. Update README/current design/methodology for the completed scope; historical Phase 0–2 validation reports should remain historical. Finish Phase 5 only when its measured acceptance criteria are met or explicitly defer live-model criteria per the offline preference.

## Final verification at pause

- Full ordinary backend suite: **314 passed, 23 skipped** (Docker tests are opt-in).
- Expanded Docker suite: **23 passed in 196.19 seconds**. This includes all 14 Phase 2 controls, full evaluation of all five fixture subjects, deterministic inventory reproduction, and rejection of failing/skipped/hanging generated output.
- `git diff --check`: passed. New guide/checkpoint links resolve.
- No frontend source was changed for Phases 3–5; the last Phase 2 production build passed.
- Hosted CI has not run; changes remain local and uncommitted.
- No additional benchmark matrix or live checks were started after the stop request. The in-flight test run finished normally.
