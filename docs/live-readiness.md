# Live trial status

Updated 2026-09-22. The user authorized a US$2–3 ceiling; both smoke evaluations used one persistent **US$2** ledger. Four API attempts cost an estimated **US$0.00104415** at standard uncached rates (1,649 input / 1,328 output tokens). The ledger reserved US$0.08663040 conservatively; this is not the billed amount.

The live smoke gate **did not pass**, so the conditional five-subject live benchmark was **not started**. Do not describe the existing five-subject fixture measurements as AI evidence.

| Evaluation | Generation | Collection | Original baselines | Mutation |
| --- | --- | --- | --- | --- |
| `contract-v1` | Three attempts rejected: schema, artifact, artifact | Not run | Not run | Not run |
| `contract-v2` | Valid pytest on first attempt | Six tests collected | Both repeats: five passed, one failed | Correctly blocked |

The original prompt did not explicitly require the full generated-directory prefix or include the response schema. `contract-v2` adds those instructions while retaining v1 unchanged. Invalid v1 responses were hashed rather than stored, so their exact defects cannot be reconstructed. No generated output was manually edited into a passing suite.

The v2 model invented a requirement that invalid input types raise `TypeError`, despite the specification explicitly placing other input types outside the contract. This is a model oracle error, not a defect in the original implementation. The whole suite was rejected after both baseline repeats failed. Collection output lists only the six generated tests; the generated artifact imports only pytest and the selected public API. Native test paths are excluded from the model context and generated execution request.

Model snapshot: `gpt-4o-mini-2024-07-18`; returned fingerprint, exact prompt/context, subject commit, runner image, artifact hashes, tokens, attempt statuses and execution observations are retained in the [published smoke evidence](../benchmarks/results/live-smoke-20260922/README.md). All context files were verified against the public repository before export. Runtime containers reported successful cleanup.

Next work: evaluate a separately versioned prompt that respects explicitly out-of-contract inputs, preserving these failures. Only a successful fresh smoke evaluation should unlock the five-subject live benchmark. Additional retries were stopped to avoid selecting a lucky passing output.
