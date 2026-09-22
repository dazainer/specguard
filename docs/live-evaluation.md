# Controlled live evaluation

The web product remains fixture-only. Use the CLI for explicitly authorized paid evaluation; never relabel handwritten fixture measurements as AI output. This workflow sends only the specification, interface and explicitly selected source files to OpenAI. Native tests are excluded from model context and from generated-suite container mounts.

The controlled adapter pins `gpt-4o-mini-2024-07-18`, 4096 maximum output tokens, 60-second request timeout, at most three generation attempts, and no nested SDK retries. Generation retries repair JSON/schema/artifact failures; failing collected/baseline tests fail the evaluation rather than triggering unlimited repair calls.

## Budget behavior

`--live` requires both `--budget-ledger` and `--max-cost-usd`. Reuse the **same ledger** for smoke and benchmark. Before every HTTP attempt, a locked, persistent ledger reserves the conservative full 128,000-token context at $0.15/million input plus 4096 tokens at $0.60/million output: **$0.0216576 per attempt**. Failed/timed-out attempts keep their reservation; a new process using the same ledger cannot reset it. A reservation exceeding the ceiling blocks the request. Only the priced pinned model is allowed with this guard.

Rates were checked against [OpenAI's model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini) on 2026-09-22. This is a conservative client-side bound at those rates, not an account-wide billing limit; taxes, price changes and independent clients are outside it. The report's token-based estimate uses standard uncached rates, so cache discounts may lower the bill. Actual provider billing is authoritative. Do not change the pricing snapshot without reviewing the reservation bound.

## Run one smoke test

The initial v1/v2 smoke evaluations failed; see [retained evidence and current status](live-readiness.md). `contract-v2` adds explicit schema and artifact-path instructions. It is a distinct prompt version, not evidence that the original prompt succeeded. The example below selects v2; further trials should preserve failed attempts and respect the stop gate.

From `backend/`, with the configured API key in private `backend/.env`, Docker running and `EVALUATION_RUNNER_IMAGE` exported to the immutable local image ID:

```bash
.venv/bin/python -m app.evaluation.evaluate \
  ../benchmarks/subjects/access_policy/specguard.yaml \
  --output ../benchmark-runs/live-smoke \
  --image "$EVALUATION_RUNNER_IMAGE" \
  --live --strategy contract-v2 --model gpt-4o-mini-2024-07-18 \
  --budget-ledger ../benchmark-runs/live-budget.json --max-cost-usd 2
```

The example authorizes up to $2 only when you deliberately run it. Use a fresh output directory, and your approved ceiling. `access_policy` has the smallest implementation in the curated set (155 bytes). A successful smoke run must have model-produced pytest, successful collection, two full passing baselines, matching native/generated mutant inventory hashes, and completed mutation results. Inspect `report.json`, `generation.json`, `attempts.json`, `prompt.json` and the execution JSON. Do not hand-edit failed model output into a success.

## Only after a successful smoke test

```bash
.venv/bin/python -m app.evaluation.benchmark \
  --subjects ../benchmarks/subjects --output ../benchmark-runs/live-five \
  --image "$EVALUATION_RUNNER_IMAGE" \
  --live --model gpt-4o-mini-2024-07-18 --trials 1 --strategies contract-v2 \
  --budget-ledger ../benchmark-runs/live-budget.json --max-cost-usd 2
```

This requests one evaluation per synthetic subject. Keep failures in the attempted denominator. Six evaluations with at most three attempts each reserve no more than **$0.3898368** at the checked rates. The smoke is separate from the five-subject benchmark; it must not be counted as an extra successful benchmark trial or used to replace a failed trial.

## Inspect and share

Reports retain requested model, returned model/fingerprint in attempts, prompt version and exact private prompts, input hashes, subject commit, image ID, suite eligibility and every mutation outcome. JSON/CSV/Markdown summaries can be published after reviewing for local paths and secrets. Raw context, model responses, generated tests, native snapshots and per-mutant logs remain under ignored `benchmark-runs/` unless deliberately reviewed for publication.

Initial one-trial results are evidence that the pipeline processed actual model output. They do not establish repeatability, superiority to native tests, prompt-strategy improvements, or external-repository generalization.
