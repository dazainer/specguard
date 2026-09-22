# Controlled live smoke evidence — 2026-09-22

Two sequential evaluations of the smallest synthetic subject, `access_policy`, using real OpenAI output. Both failed, at different gates. These are not five-subject benchmark results and are not evidence of a live mutation score.

- `v1/`: original `contract-v1`, three rejected generation attempts. Exact rejected bodies were not retained; hashes, byte counts, model/fingerprint, token usage and coarse validation categories were retained.
- `v2/`: `contract-v2` makes the JSON schema and artifact path contract explicit. The first response produced six executable tests, but one invented an exception requirement. Both original baseline repeats failed (five passed, one failed), so mutation was not run.
- `budget.json`: shared US$2 reservation ledger for all four HTTP attempts.
- `cost.json`: total estimated usage; provider billing is authoritative.

Published prompts and context contain only reviewed public benchmark inputs. Valid generated source is retained unchanged in `v2/generation.json`. Container names were omitted from the published execution JSON; observations are otherwise retained. The raw runs remain in ignored local `benchmark-runs/` directories.

See [analysis and next gate](../../../docs/live-readiness.md). No failing model output was repaired by hand, no failed trial was replaced by a successful one, and no native tests were included in the collected generated suite.
