"""Reproducible specification → generation → baseline → mutation CLI."""
import argparse
import asyncio
import json
from pathlib import Path
import statistics
import time

from app.evaluation.context_builder import canonical_json, sha256
from app.evaluation.control import EvaluationStopped
from app.evaluation.execution_runner import DockerRunner
from app.evaluation.generation import generate, PROMPTS
from app.evaluation.manifest import Manifest, load_manifest
from app.evaluation.mutation import mutation_sources, parse_inventory, evaluate_mutants
from app.evaluation.mutation_cache import cache_key, read_cache, write_cache
from app.evaluation.observations import observe, all_passed
from app.evaluation.paths import beneath
from app.evaluation.prepare import prepare
from app.evaluation.providers import FixtureProvider, OpenAIProvider
from app.schemas.evaluation import ArtifactRecord, BaselineRun, EvaluationReport, SuiteReport
from app.schemas.execution import ExecutionRequest


def save_report(report, output):
    validated = EvaluationReport.model_validate(report.model_dump())
    temporary = output / 'report.tmp'
    temporary.write_text(validated.model_dump_json(indent=2) + '\n')
    temporary.replace(output / 'report.json')
    return validated


def request_for(manifest, output, suite):
    selections = set(manifest.context.source_files + manifest.mutation.source_paths)
    source = sorted(path for path in selections if not any(beneath(path, other) for other in selections if path != other))
    return ExecutionRequest(target_snapshot=output / 'target', source_paths=source,
                            test_workspace=output / ('target' if suite == 'native' else 'generated'),
                            test_paths=manifest.tests.native_paths if suite == 'native' else [manifest.tests.generated_path],
                            command=manifest.tests.baseline_command, limits=manifest.limits,
                            timeout_seconds=manifest.tests.timeout_seconds)


def gate_suite(runner, request, repeats, output, suite, progress=None):
    if progress:
        progress('collecting')
    collected = runner.run(request.model_copy(update={'mode': 'collect'}))
    (output / f'{suite}-collection.json').write_text(collected.model_dump_json(indent=2))
    observed = observe(collected)
    count = observed.collected if observed else None
    if collected.status != 'passed' or observed is None or not count or observed.errors or observed.skipped:
        return SuiteReport(collection_status='failed', collected_tests=count), 'collection_' + (collected.status if collected.status != 'passed' else 'invalid_observations')
    runs = []
    if progress:
        progress('baseline_running')
    for index in range(repeats):
        result = runner.run(request)
        (output / f'{suite}-baseline-{index + 1}.json').write_text(result.model_dump_json(indent=2))
        observation = observe(result)
        status = result.status if result.status != 'passed' or all_passed(result, count) else 'failed'
        runs.append(BaselineRun(status=status, collected_tests=observation.collected if observation else None,
                                passed_tests=observation.passed if observation else None,
                                failed_tests=observation.failed if observation else None,
                                duration_seconds=result.duration_seconds))
    passed = all(run.status == 'passed' for run in runs)
    statuses = {run.status for run in runs}
    reason = None if passed else ('baseline_flaky' if 'passed' in statuses else 'baseline_' + runs[0].status)
    return SuiteReport(collection_status='passed', collected_tests=count,
                       accepted_tests=count if passed else 0, rejected_tests=0 if passed else count,
                       baseline_runs=runs, baseline_pass_rate=sum(run.status == 'passed' for run in runs) / len(runs),
                       repeat_duration_variance_seconds2=statistics.pvariance(run.duration_seconds for run in runs)), reason


async def evaluate(manifest_path, output, image, *, provider=None, fixture=None, strategy='contract-v1',
                   live=False, model='gpt-4o-mini', context_mode=None, mutate=True, runner=None, cache_dir=None, progress=None):
    started = time.monotonic()
    original = load_manifest(manifest_path)
    data = original.model_dump()
    data['generation'].update(provider='openai' if live else 'fixture',
                              model=model if live else 'handwritten-fixture-v1', prompt_version=strategy)
    if context_mode:
        data['context']['mode'] = context_mode
        if context_mode == 'spec_only':
            data['context']['source_files'] = []
    manifest = Manifest.model_validate(data)
    report = prepare(manifest_path, output, manifest_override=manifest)
    output = output.resolve()
    runner = runner or DockerRunner(image)
    report = report.model_copy(update={'status': 'generating', 'provenance': report.provenance.model_copy(update={'runner_image_digest': image})})
    report = save_report(report, output)
    if progress:
        progress(report)
    def set_stage(stage):
        nonlocal report
        report = save_report(report.model_copy(update={'status': stage}), output)
        if progress:
            progress(report)
    own_provider = provider is None
    timings = {}
    try:
        provider = provider or (OpenAIProvider() if live else FixtureProvider(fixture or manifest_path.parent / 'generation-fixture.json'))
        context = json.loads((output / 'context.json').read_text())
        artifacts, metrics = await generate(provider, manifest, context, output)
        report = report.model_copy(update={'generation': metrics})
        timings['generation'] = metrics.duration_seconds
        if artifacts is None:
            raise ValueError('generation_failed')
        for artifact in artifacts:
            path = output / 'generated' / artifact.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(artifact.content)
        report = report.model_copy(update={'artifacts': [ArtifactRecord(path=a.path, sha256=a.sha256, size_bytes=a.size_bytes) for a in artifacts], 'status': 'collecting'})
        report = save_report(report, output)
        for suite in ('generated', 'native'):
            stage = time.monotonic()
            result, failure = gate_suite(runner, request_for(manifest, output, suite), manifest.tests.repeat_count, output, suite, set_stage)
            runtime = json.loads((output / f'{suite}-collection.json').read_text())['runtime']
            provenance = report.provenance.model_copy(update={'python_version': runtime.get('python', report.provenance.python_version),
                'tool_versions': report.provenance.tool_versions | runtime})
            report = save_report(report.model_copy(update={suite: result, 'provenance': provenance}), output)
            timings[suite + '_baseline'] = time.monotonic() - stage
            if failure:
                if suite == 'generated':
                    (output / 'generated').rename(output / 'quarantine')
                raise ValueError(suite + '_' + failure)
        if mutate:
            set_stage('mutating')
            request = request_for(manifest, output, 'native')
            sources = mutation_sources(manifest, output / 'target')
            inventory_request = request.model_copy(update={'mode': 'inventory', 'mutation_paths': sources,
                'timeout_seconds': manifest.mutation.timeout_seconds,
                'limits': manifest.limits.model_copy(update={'output_kb': 16384})})
            stage = time.monotonic()
            raw = runner.run(inventory_request)
            (output / 'inventory-execution.json').write_text(raw.model_dump_json(indent=2))
            mutants = parse_inventory(raw, sources)
            inventory = {'engine': 'mutmut', 'version': '2.4.4', 'mutants': [m.model_dump() for m in mutants]}
            inventory_bytes = canonical_json(inventory)
            (output / 'inventory.json').write_bytes(inventory_bytes)
            timings['inventory'] = time.monotonic() - stage
            configuration = {'engine': 'mutmut-2.4.4', 'image': image, 'source_paths': sources,
                             'excluded_paths': manifest.mutation.excluded_paths, 'limits': manifest.limits.model_dump(),
                             'timeout_seconds': manifest.mutation.timeout_seconds, 'command': manifest.tests.baseline_command}
            (output / 'mutation-config.json').write_bytes(canonical_json(configuration))
            for suite in ('native', 'generated'):
                request = request_for(manifest, output, suite).model_copy(update={'timeout_seconds': manifest.mutation.timeout_seconds})
                records_path = output / f'{suite}-mutants.jsonl'
                inventory_hash, config_hash = sha256(inventory_bytes), sha256(canonical_json(configuration))
                key = cache_key(request, image, inventory_hash, config_hash, manifest.repository.commit)
                cached = read_cache(cache_dir, key, mutants, records_path) if cache_dir and suite == 'native' else None
                if cached:
                    summary, metadata = cached
                    if summary.inventory_sha256 != inventory_hash or summary.configuration_sha256 != config_hash:
                        raise ValueError('cache_provenance_mismatch')
                else:
                    summary = evaluate_mutants(runner, request, mutants, getattr(report, suite).collected_tests,
                                               records_path, inventory_hash, config_hash)
                    metadata = dict(hit=False, key=key)
                    if cache_dir and suite == 'native':
                        write_cache(cache_dir, key, summary, records_path, report.run_id)
                (output / f'{suite}-cache.json').write_text(json.dumps(metadata, indent=2))
                timings[suite + '_mutation'] = summary.duration_seconds
                report = save_report(report.model_copy(update={suite: getattr(report, suite).model_copy(update={'mutation': summary})}), output)
        report = report.model_copy(update={'status': 'completed'})
    except EvaluationStopped as error:
        report = report.model_copy(update={'status': 'cancelled' if error.reason == 'cancelled' else 'failed', 'failure_reason': error.reason})
    except (Exception, KeyboardInterrupt) as error:
        # Never copy provider bodies or validation inputs to the public failure field.
        reason = str(error) if isinstance(error, ValueError) and str(error).replace('_', '').isalnum() and len(str(error)) < 100 else type(error).__name__
        report = report.model_copy(update={'status': 'failed', 'failure_reason': reason})
    finally:
        if own_provider and isinstance(provider, OpenAIProvider):
            await provider.close()
        timings['total'] = time.monotonic() - started
        (output / 'timings.json').write_text(json.dumps(timings, indent=2))
        report = save_report(report, output)
        from app.evaluation.reporting import write_run_summary
        write_run_summary(report, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--image', required=True)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--live', action='store_true', help='Use the configured OpenAI key; incurs API usage')
    parser.add_argument('--model', default='gpt-4o-mini')
    parser.add_argument('--strategy', choices=tuple(PROMPTS), default='contract-v1')
    parser.add_argument('--context', choices=('spec_only', 'spec_plus_code'))
    parser.add_argument('--baseline-only', action='store_true')
    parser.add_argument('--cache-dir', type=Path, help='Optional local native-mutation cache; baselines always rerun')
    args = parser.parse_args()
    if args.live and args.fixture:
        parser.error('--live and --fixture are mutually exclusive')
    try:
        report = asyncio.run(evaluate(args.manifest, args.output, args.image, fixture=args.fixture,
                                      strategy=args.strategy, live=args.live, model=args.model,
                                      context_mode=args.context, mutate=not args.baseline_only, cache_dir=args.cache_dir))
    except (ValueError, OSError):
        parser.exit(2, 'Evaluation setup failed; check manifest, image ID, and new output path.\n')
    print(json.dumps({'status': report.status, 'failure_reason': report.failure_reason, 'output': str(args.output)}))
    raise SystemExit(0 if report.status == 'completed' else 1)


if __name__ == '__main__':
    main()
