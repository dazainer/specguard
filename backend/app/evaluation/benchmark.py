"""Sequential pinned-subject matrix with explicit failures, variance and export formats."""
import argparse
import asyncio
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import platform
import statistics
import time

from app.evaluation.context_builder import canonical_json, sha256
from app.evaluation.evaluate import evaluate
from app.evaluation.generation import PROMPTS


def summarize(output, records, environment):
    (output / 'results.json').write_text(json.dumps(records, indent=2))
    (output / 'environment.json').write_text(json.dumps(environment, indent=2))
    failures = Counter(record['failure_reason'] for record in records if record['status'] != 'completed')
    (output / 'failures.json').write_text(json.dumps(dict(failures), indent=2))
    groups = defaultdict(list)
    for record in records:
        groups[(record['subject'], record['provider'], record['strategy'])].append(record)
    aggregates = []
    for (subject, provider, strategy), runs in groups.items():
        scores = [run['generated_score'] for run in runs if run['status'] == 'completed' and run['generated_score'] is not None]
        times = [run['duration_seconds'] for run in runs]
        aggregates.append(dict(subject=subject, provider=provider, strategy=strategy, attempted=len(runs),
            completed=sum(run['status'] == 'completed' for run in runs), score_n=len(scores),
            score_mean=statistics.mean(scores) if scores else None,
            score_variance=statistics.pvariance(scores) if len(scores) >= 2 else None,
            duration_mean=statistics.mean(times), duration_variance=statistics.pvariance(times) if len(times) >= 2 else None))
    (output / 'aggregates.json').write_text(json.dumps(aggregates, indent=2))
    if records:
        with (output / 'results.csv').open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    lines = ['# Benchmark measurements', '',
        'First-party synthetic subjects; this is not a sample of independent external repositories. Fixture runs are not model-quality evidence.', '',
        '| Subject | Provider | Prompt | Completed / attempted | Eligible scores | Mean score | Score variance | Mean seconds |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in aggregates:
        score = f"{row['score_mean']:.4f}" if row['score_mean'] is not None else 'unmeasured'
        variance = f"{row['score_variance']:.6f}" if row['score_variance'] is not None else 'unmeasured'
        lines.append(f"| {row['subject']} | {row['provider']} | {row['strategy']} | {row['completed']} / {row['attempted']} | {row['score_n']} | {score} | {variance} | {row['duration_mean']:.2f} |")
    lines += ['', 'Mutation score = killed / (killed + survived). Each run retains the denominator and timeout/invalid/error/suspicious counts in results.csv and report.json.',
              'Variance is population variance across eligible trials; null means fewer than two observations. Failed trials remain in the attempted denominator.',
              'Native mutation caching, if enabled, is identified per run; original observations and source run IDs are retained.',
              '', 'Failures: `' + json.dumps(dict(failures), sort_keys=True) + '`']
    (output / 'summary.md').write_text('\n'.join(lines) + '\n')


async def benchmark(subjects, output, image, *, live=False, model='gpt-4o-mini', trials=1,
                    strategies=('contract-v1',), cache_dir=None):
    if output.exists():
        raise ValueError('Benchmark output must be a new directory')
    manifests = sorted(subjects.glob('*/specguard.yaml'))
    if not manifests:
        raise ValueError('No subject manifests found')
    output.mkdir(parents=True, mode=0o700)
    records = []
    code_root = Path(__file__).resolve().parents[2]
    code_paths = sorted(list((code_root / 'app/evaluation').glob('*.py')) + list((code_root.parent / 'docker/runner').glob('*')))
    environment = dict(image=image, host_python=platform.python_version(), host_platform=platform.platform(),
        engine='mutmut-2.4.4', trials=trials, strategies=list(strategies), provider='openai' if live else 'fixture',
        model=model if live else 'handwritten-fixture-v1', native_cache_enabled=cache_dir is not None,
        implementation_sha256=sha256(canonical_json({str(path.relative_to(code_root.parent)): sha256(path.read_bytes()) for path in code_paths if path.is_file()})))
    for manifest in manifests:
        for strategy in strategies:
            for trial in range(1, trials + 1):
                run_name = f'{manifest.parent.name}-{strategy}-{trial}'
                run_output = output / run_name
                started = time.monotonic()
                print(f'Starting {run_name}', flush=True)
                try:
                    report = await evaluate(manifest, run_output, image, live=live, model=model,
                                             strategy=strategy, cache_dir=cache_dir)
                    record = dict(subject=manifest.parent.name, strategy=strategy, trial=trial,
                        provider=report.generation_config.provider, model=report.generation_config.model,
                        status=report.status, failure_reason=report.failure_reason,
                        commit=report.provenance.repository_commit, run_id=report.run_id,
                        generation_successful=report.generation.successful,
                        generation_attempts=report.generation.attempts,
                        input_tokens=report.generation.input_tokens, output_tokens=report.generation.output_tokens)
                    for suite in ('native', 'generated'):
                        data = getattr(report, suite)
                        record[suite + '_collected'] = data.collected_tests
                        record[suite + '_baseline_pass_rate'] = data.baseline_pass_rate
                        for key in ('generated', 'killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious', 'denominator', 'score'):
                            record[suite + '_' + key] = getattr(data.mutation, key) if data.mutation else None
                    record['native_cache_hit'] = json.loads((run_output / 'native-cache.json').read_text())['hit'] if (run_output / 'native-cache.json').exists() else False
                    environment['runtime'] = report.provenance.tool_versions
                except (ValueError, OSError) as error:
                    # Persist setup failures too; never silently skip a subject.
                    record = dict(subject=manifest.parent.name, strategy=strategy, trial=trial,
                        provider='openai' if live else 'fixture', model=model if live else 'handwritten-fixture-v1',
                        status='failed', failure_reason='setup_' + type(error).__name__, commit=None, run_id=None,
                        generation_successful=None, generation_attempts=0, input_tokens=None, output_tokens=None)
                    for suite in ('native', 'generated'):
                        for key in ('collected', 'baseline_pass_rate', 'generated', 'killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious', 'denominator', 'score'):
                            record[suite + '_' + key] = None
                    record['native_cache_hit'] = False
                record.update(duration_seconds=time.monotonic() - started, artifact_directory=run_name)
                records.append(record)
                summarize(output, records, environment)
                print(f"Finished {run_name}: {record['status']} ({record['duration_seconds']:.1f}s)", flush=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subjects', type=Path, default=Path('../benchmarks/subjects'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--model', default='gpt-4o-mini')
    parser.add_argument('--trials', type=int, choices=range(1, 11), default=1)
    parser.add_argument('--strategies', nargs='+', choices=tuple(PROMPTS), default=['contract-v1'])
    parser.add_argument('--cache-dir', type=Path)
    args = parser.parse_args()
    records = asyncio.run(benchmark(args.subjects, args.output, args.image, live=args.live, model=args.model,
                                    trials=args.trials, strategies=tuple(args.strategies), cache_dir=args.cache_dir))
    raise SystemExit(0 if all(record['status'] == 'completed' for record in records) else 1)


if __name__ == '__main__':
    main()
