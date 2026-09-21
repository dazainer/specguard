"""Offline preparation command. Does not execute target code or generated tests."""

import argparse
import importlib.metadata
import json
import os
import platform
import tempfile
import uuid
from pathlib import Path

from app.evaluation.artifact_validator import validate_artifacts
from app.evaluation.context_builder import build_context, canonical_json, sha256
from app.evaluation.manifest import Manifest, load_manifest
from app.evaluation.paths import overlap, safe_path
from app.evaluation.snapshot import export_bundle, git
from app.schemas.evaluation import ArtifactRecord, EvaluationReport, ExecutableTestGenerationResult, Provenance


def prepare(manifest_path: Path, output: Path, *, fixture: Path | None = None, manifest_override: Manifest | None = None) -> EvaluationReport:
    manifest = manifest_override or load_manifest(manifest_path)
    root = manifest_path.parent.resolve()
    if not manifest.repository.bundle:
        raise ValueError("Phase 1 prepares local bundles only; remote repository fetching is not implemented")
    if fixture is not None and manifest.generation.provider != "fixture":
        raise ValueError("fixture artifacts require provider=fixture")
    if output.exists() or output.is_symlink():
        raise ValueError("output must be a new directory")
    # The caller deliberately selects a new directory, typically under /tmp.
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    bundle = safe_path(root, manifest.repository.bundle, must_exist=True)
    with tempfile.TemporaryDirectory(prefix=".specguard-prepare-", dir=output.parent) as directory:
        staging = Path(directory)
        snapshot = staging / "target"
        export_bundle(bundle, manifest.repository.commit, snapshot)
        for relative in (
            manifest.tests.native_paths + manifest.mutation.source_paths
            + manifest.mutation.excluded_paths + [manifest.environment.dependency_lock]
        ):
            safe_path(snapshot, relative, must_exist=True)
        if safe_path(snapshot, manifest.tests.generated_path).exists():
            raise ValueError("target snapshot already contains the generated directory")
        context = build_context(manifest, root, snapshot)
        context_bytes = canonical_json(context)
        manifest_bytes = canonical_json(manifest.model_dump())
        lock = safe_path(snapshot, manifest.environment.dependency_lock, must_exist=True)
        if not lock.is_file():
            raise ValueError("dependency lock must be a regular file")
        report = EvaluationReport(
            run_id=str(uuid.uuid4()), status="prepared", context_mode=manifest.context.mode,
            generation_config=manifest.generation,
            required_baseline_repeats=manifest.tests.repeat_count,
            provenance=Provenance(
                repository_commit=manifest.repository.commit,
                manifest_sha256=sha256(manifest_bytes),
                specification_sha256=sha256(context["specification"].encode()),
                context_sha256=sha256(context_bytes),
                dependency_lock_sha256=sha256(lock.read_bytes()),
                python_version=manifest.environment.python_version,
                tool_versions={
                    **{name: importlib.metadata.version(name) for name in ("pydantic", "PyYAML")},
                    "git": git("--version", cwd=root).decode().strip(),
                    "preparation_python": platform.python_version(),
                },
            ),
        )
        if fixture is not None:
            if fixture.is_symlink() or not fixture.is_file() or fixture.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("fixture must be a regular JSON file at most 2 MiB")
            result = ExecutableTestGenerationResult.model_validate_json(fixture.read_bytes())
            workspace = staging / "generated"
            workspace.mkdir()
            artifacts = validate_artifacts(result, manifest, workspace)
            for artifact in artifacts:
                if any(overlap(artifact.path, str(path.relative_to(snapshot))) for path in snapshot.rglob("*") if path.is_file()):
                    raise ValueError("generated artifact conflicts with target snapshot")
                path = safe_path(workspace, artifact.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(artifact.content, encoding="utf-8", newline="\n")
                report.artifacts.append(ArtifactRecord(
                    path=artifact.path, sha256=artifact.sha256, size_bytes=artifact.size_bytes,
                ))
            (staging / "generation-fixture.json").write_text(result.model_dump_json(indent=2) + "\n")
        (staging / "manifest.json").write_bytes(manifest_bytes)
        (staging / "context.json").write_bytes(context_bytes)
        (staging / "report.json").write_text(report.model_dump_json(indent=2) + "\n")
        # Rename only after every validation succeeds; failures leave no partial run.
        os.rename(staging, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.manifest, args.output, fixture=args.fixture)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Preparation failed: {error}\n")
    print(json.dumps({"status": report.status, "run_id": report.run_id, "output": str(args.output)}))


if __name__ == "__main__":
    main()
