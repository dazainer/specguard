"""Adapt pinned mutmut-generated source variants to the existing isolated runner."""
import json
from pathlib import Path
import tempfile
import time
from collections import Counter

from pydantic import Field

from app.evaluation.context_builder import canonical_json, sha256
from app.evaluation.execution_workspace import stage_selection
from app.evaluation.manifest import SHA256, StrictModel
from app.evaluation.observations import all_passed, observe
from app.evaluation.paths import RelativePath, beneath
from app.schemas.evaluation import MutationSummary


class Mutant(StrictModel):
    id: SHA256
    source_file: RelativePath
    line: int = Field(ge=1)
    operator: str = Field(min_length=1, max_length=128)
    diff: str = Field(max_length=1048576)
    content: str = Field(max_length=4194304)
    valid: bool


def parse_inventory(result, sources):
    if result.status != 'passed' or result.output_truncated:
        raise ValueError('mutation_inventory_execution_failed')
    data = json.loads(result.stdout)
    if data.get('engine') != 'mutmut' or data.get('version') != '2.4.4':
        raise ValueError('mutation_engine_version_mismatch')
    mutants = [Mutant.model_validate(value) for value in data['mutants']]
    if not mutants or len(mutants) > 1000 or len({m.id for m in mutants}) != len(mutants):
        raise ValueError('invalid_or_empty_mutation_inventory')
    if any(mutant.source_file not in sources for mutant in mutants):
        raise ValueError('mutation_source_mismatch')
    return mutants


def mutation_sources(manifest, target):
    files = set()
    for relative in manifest.mutation.source_paths:
        path = target / relative
        candidates = path.rglob('*.py') if path.is_dir() else [path]
        for candidate in candidates:
            name = candidate.relative_to(target).as_posix()
            if name.endswith('.py') and not any(name == excluded or beneath(name, excluded) for excluded in manifest.mutation.excluded_paths):
                files.add(name)
    if not files or len(files) > 32:
        raise ValueError('mutation requires 1–32 selected Python files')
    return sorted(files)


def outcome(result, collected):
    if result.status == 'timeout':
        return 'timed_out'
    if result.status in {'infrastructure_error', 'resource_limit', 'collection_error'}:
        return 'errors'
    if result.status == 'failed' and result.exit_code != 1:
        return 'errors'
    observation = observe(result)
    if observation is None or observation.collected != collected or observation.skipped or observation.errors:
        return 'suspicious'
    if all_passed(result, collected):
        return 'survived'
    if result.status == 'failed' and result.exit_code == 1 and observation.failed > 0:
        return 'killed'
    return 'errors'


def evaluate_mutants(runner, request, mutants, collected, output: Path, inventory_hash, configuration_hash):
    started = time.monotonic()
    records = []
    # Every mutant gets a new container. No mutation operators or worker pool
    # are implemented here; mutmut supplies all source transformations.
    for mutant in mutants:
        entry = mutant.model_dump(exclude={'content', 'valid'})
        entry.update(manual_review='unreviewed', review_notes=None, killing_test=None,
                     duration_seconds=0.0, status='invalid', execution=None)
        if mutant.valid:
            with tempfile.TemporaryDirectory(prefix='specguard-mutant-') as directory:
                source = Path(directory) / 'source'
                stage_selection(request.target_snapshot, request.source_paths, source)
                path = source / mutant.source_file
                path.chmod(0o644)
                path.write_text(mutant.content)
                path.chmod(0o444)
                changed = request.model_copy(update={'target_snapshot': source})
                result = runner.run(changed)
            entry.update(status=outcome(result, collected), duration_seconds=result.duration_seconds,
                         execution=result.model_dump())
            observation = observe(result)
            if entry['status'] == 'killed' and observation and observation.failing_tests:
                entry['killing_test'] = observation.failing_tests[0]
        records.append(entry)
        # Incremental artifacts survive interruption; partial runs are not scores.
        with output.open('a') as file:
            file.write(json.dumps(entry) + '\n')
    counts = Counter(record['status'] for record in records)
    denominator = counts['killed'] + counts['survived']
    return MutationSummary(inventory_sha256=inventory_hash, configuration_sha256=configuration_hash,
                           generated=len(mutants), **{key: counts[key] for key in ('killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious')},
                           denominator=denominator, score=counts['killed'] / denominator if denominator else None,
                           duration_seconds=time.monotonic() - started)
