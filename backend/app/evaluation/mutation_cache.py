"""Optional native-suite result reuse, keyed by all execution inputs after baseline gating."""
import json
from pathlib import Path
import time
import uuid

from app.evaluation.context_builder import canonical_json, sha256
from app.schemas.evaluation import MutationSummary


def cache_key(request, image, inventory_hash, configuration_hash, commit):
    def selected_hashes(root, selected):
        hashes = {}
        for relative in selected:
            path = root / relative
            for candidate in sorted(path.rglob('*')) if path.is_dir() else [path]:
                if candidate.is_file():
                    hashes[candidate.relative_to(root).as_posix()] = sha256(candidate.read_bytes())
        return hashes
    return sha256(canonical_json(dict(protocol='native-cache-v1', image=image, commit=commit,
        inventory=inventory_hash, configuration=configuration_hash,
        source=selected_hashes(request.target_snapshot, request.source_paths),
        tests=selected_hashes(request.test_workspace, request.test_paths))))


def read_cache(directory, key, mutants, output):
    started = time.monotonic()
    path = directory / (key + '.json')
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
        return None
    try:
        data = json.loads(path.read_text())
        if data['key'] != key or sha256(data['records'].encode()) != data['records_sha256']:
            return None
        summary = MutationSummary.model_validate(data['summary'])
        records = [json.loads(line) for line in data['records'].splitlines()]
        if [record['id'] for record in records] != [mutant.id for mutant in mutants]:
            return None
        if summary.errors or summary.suspicious or summary.timed_out:
            return None
        if any(sum(record['status'] == status for record in records) != getattr(summary, status)
               for status in ('killed', 'survived', 'invalid', 'errors', 'suspicious', 'timed_out')):
            return None
        output.write_text(data['records'])
        metadata = dict(hit=True, key=key, source_run=data['source_run'], original_duration_seconds=summary.duration_seconds)
        return summary.model_copy(update={'duration_seconds': time.monotonic() - started}), metadata
    except (ValueError, KeyError, TypeError, OSError):
        return None


def write_cache(directory, key, summary, records_path, run_id):
    if summary.errors or summary.suspicious or summary.timed_out:
        return
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = records_path.read_text()
    data = dict(key=key, summary=summary.model_dump(), records=records,
                records_sha256=sha256(records.encode()), source_run=run_id)
    temporary = directory / ('.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(data))
    temporary.replace(directory / (key + '.json'))
