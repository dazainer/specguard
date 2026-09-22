# Live trial readiness

Prepared 2026-09-22. The live smoke test and five-subject live benchmark have **not run yet**: the numeric API spending ceiling is awaiting the user's answer. Do not describe fixture data as live AI evidence.

Ready components:

- Existing API key detected without displaying it; pinned runner image available locally.
- Smallest synthetic implementation selected: `access_policy` (155 bytes).
- Persistent cumulative spend guard, model snapshot pin, output cap, bounded attempts and token/cost provenance implemented.
- Budget tests include concurrency, persisted ledger reuse, exhaustion, malformed limits and no refund after an interrupted transport call.
- Final backend suite: **340 passed, 27 opt-in Docker skips**. Four fixture product Docker checks passed after the adapter changes. Frontend: **23 passed**, native and Node 22 Docker builds passed; 12 real-data browser accessibility/viewport checks passed.

After budget approval, follow [the controlled live guide](live-evaluation.md), sharing one ledger between the smoke and one-trial five-subject benchmark. Proceed to the benchmark only if the smoke completes generation, collection, repeated baselines and mutation. Publish actual results including failures and update this readiness note. No extra live repeats or external-target model calls are preapproved by that test recipe.
