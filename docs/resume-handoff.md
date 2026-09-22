# SpecGuard — factual handoff for résumé/portfolio drafting

Public repository: https://github.com/dazainer/specguard

The project now evaluates executable pytest suites against pinned Python implementations. It validates generated artifacts, collects tests, requires two passing original baselines, and compares native/generated suites on the same mutation inventory. Failed baselines remain failures and receive no mutation score.

Verified engineering work:

- FastAPI backend, React/TypeScript frontend, SQLite/Alembic durable evaluation queue, separate worker, cancellation, crash recovery, artifact retention and JSON/Markdown/CSV exports.
- Non-root Docker execution with disabled networking, read-only inputs/root filesystem, dropped capabilities and bounded CPU, memory, processes, scratch space, output and time. This is a local/private application, not a hardened public multi-tenant service.
- Pinned subject commits, immutable runner image IDs, content hashes, prompt/model provenance, repeated baselines and explicit excluded mutation outcomes.
- Responsive UI checked at 375, 768 and 1440 pixels; keyboard workflow, reduced motion and automated axe accessibility checks. These checks do not certify complete accessibility conformance.
- GitHub CI for backend, frontend build/tests and Docker integration. Latest local backend suite: 341 passed with 27 opt-in Docker tests skipped; frontend: 23 passed. The preceding public CI revision passed all three jobs, including Docker integration.
- Persistent, concurrency-safe live API spend reservations, bounded retries, pinned model, token accounting and estimated costs.

Evidence that can be cited with its limitations:

1. **20 completed offline evaluations across five synthetic subjects**, two configurations × two trials, using handwritten generated-suite fixtures. This validates the evaluator; it is not model-quality or prompt-comparison evidence. See [Phase 5](phase-5-validation.md).
2. Three local cache trials averaged **77.1 seconds cold versus 43.2 seconds warm** for one subject (about 44% lower elapsed time). This is a narrow local measurement, not an application-wide speed claim.
3. **Two pinned external modules from one real repository, boltons**, evaluated with handwritten fixtures. Do not describe these as two independent repositories or live AI evaluations. See [external validation](external-target-validation.md).
4. **Live OpenAI generation and baseline rejection were exercised:** the revised smoke produced six collected tests; five passed and one failed in both original baseline repeats because the model invented an out-of-contract exception requirement. The system blocked mutation. The five-subject live benchmark has not run. See [live status](live-readiness.md).

Do not claim that AI tests beat native suites, achieve the published fixture mutation scores, generalize across repositories, or completed a live five-subject benchmark. The strongest current résumé emphasis is reproducible evaluation infrastructure, isolated execution, durable workflows and transparent evidence. Long-term trend charts and paginated run history remain outside the implemented Phase 7 scope.
