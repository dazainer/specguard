"""Render measurements without silently hiding excluded mutant outcomes."""
import csv


def rows(report):
    for name in ('native', 'generated'):
        suite = getattr(report, name)
        mutation = suite.mutation
        yield dict(suite=name, collected=suite.collected_tests, baseline_pass=suite.baseline_pass_rate,
                   **{key: getattr(mutation, key) if mutation else None for key in
                      ('killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious', 'denominator', 'score')})


def write_run_summary(report, output):
    data = list(rows(report))
    with (output / 'summary.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    lines = [f'# Evaluation {report.run_id}', '', f'Status: **{report.status}**. Provider: `{report.generation_config.provider}`. Prompt: `{report.generation_config.prompt_version}`.',
             '', '| ' + ' | '.join(data[0]) + ' |', '| ' + ' | '.join('---' for _ in data[0]) + ' |']
    lines += ['| ' + ' | '.join('unmeasured' if value is None else str(round(value, 4)) if isinstance(value, float) else str(value) for value in row.values()) + ' |' for row in data]
    lines += ['', 'Score = killed / (killed + survived). Timeouts, invalid, errors and suspicious mutants are excluded and shown separately.',
              'Fixture suites are handwritten and are not model-quality evidence. Equivalent mutants remain unreviewed.',
              f'Failure: {report.failure_reason or "none"}.']
    (output / 'summary.md').write_text('\n'.join(lines) + '\n')
