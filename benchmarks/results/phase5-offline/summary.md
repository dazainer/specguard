# Benchmark measurements

First-party synthetic subjects; this is not a sample of independent external repositories. Fixture runs are not model-quality evidence.

| Subject | Provider | Prompt | Completed / attempted | Eligible scores | Mean score | Score variance | Mean seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| access_policy | fixture | contract-v1 | 2 / 2 | 2 | 0.8571 | 0.000000 | 15.41 |
| access_policy | fixture | boundary-v1 | 2 / 2 | 2 | 0.8571 | 0.000000 | 9.85 |
| first_subject | fixture | contract-v1 | 2 / 2 | 2 | 0.5577 | 0.000000 | 70.15 |
| first_subject | fixture | boundary-v1 | 2 / 2 | 2 | 0.5577 | 0.000000 | 38.05 |
| intervals | fixture | contract-v1 | 2 / 2 | 2 | 0.5000 | 0.000000 | 11.08 |
| intervals | fixture | boundary-v1 | 2 / 2 | 2 | 0.5000 | 0.000000 | 7.93 |
| pagination | fixture | contract-v1 | 2 / 2 | 2 | 0.6154 | 0.000000 | 16.00 |
| pagination | fixture | boundary-v1 | 2 / 2 | 2 | 0.6154 | 0.000000 | 12.52 |
| shipping | fixture | contract-v1 | 2 / 2 | 2 | 0.2308 | 0.000000 | 16.51 |
| shipping | fixture | boundary-v1 | 2 / 2 | 2 | 0.2308 | 0.000000 | 13.79 |

Mutation score = killed / (killed + survived). Each run retains the denominator and timeout/invalid/error/suspicious counts in results.csv and report.json.
Variance is population variance across eligible trials; null means fewer than two observations. Failed trials remain in the attempted denominator.
Native mutation caching, if enabled, is identified per run; original observations and source run IDs are retained.

Failures: `{}`
