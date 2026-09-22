# Benchmark measurements

Subject provenance is defined by each manifest and any upstream.json. Count external repositories separately from module subjects. Fixture runs are not model-quality evidence.

| Subject | Provider | Prompt | Completed / attempted | Eligible scores | Mean score | Score variance | Mean seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boltons_mathutils | fixture | contract-v1 | 1 / 1 | 1 | 0.5273 | unmeasured | 163.91 |
| boltons_typeutils | fixture | contract-v1 | 1 / 1 | 1 | 0.3200 | unmeasured | 43.81 |

Mutation score = killed / (killed + survived). Each run retains the denominator and timeout/invalid/error/suspicious counts in results.csv and report.json.
Variance is population variance across eligible trials; null means fewer than two observations. Failed trials remain in the attempted denominator.
Native mutation caching, if enabled, is identified per run; original observations and source run IDs are retained.

Failures: `{}`
