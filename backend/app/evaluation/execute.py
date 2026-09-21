"""Run one selected suite from a Phase 1 prepared directory inside Docker."""

import argparse
from pathlib import Path

from app.evaluation.execution_runner import DockerRunner
from app.evaluation.manifest import Manifest
from app.evaluation.paths import beneath
from app.schemas.execution import ExecutionRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--image", required=True, help="Immutable local image ID, sha256:...")
    parser.add_argument("--suite", choices=("native", "generated"), required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional new JSON result file")
    args = parser.parse_args()
    try:
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise ValueError("result output must be a new file")
        manifest = Manifest.model_validate_json((args.prepared / "manifest.json").read_bytes())
        selections = set(manifest.context.source_files + manifest.mutation.source_paths)
        source_paths = sorted(path for path in selections if not any(beneath(path, other) for other in selections if path != other))
        generated = args.suite == "generated"
        request = ExecutionRequest(
            target_snapshot=args.prepared / "target",
            test_workspace=args.prepared / ("generated" if generated else "target"),
            source_paths=source_paths,
            test_paths=[manifest.tests.generated_path] if generated else manifest.tests.native_paths,
            command=manifest.tests.baseline_command,
            mode="collect" if args.collect_only else "run",
            timeout_seconds=manifest.tests.timeout_seconds, limits=manifest.limits,
        )
        result = DockerRunner(args.image).run(request)
        serialized = result.model_dump_json(indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(serialized)
        else:
            print(serialized, end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Execution setup failed: {error}\n")
    raise SystemExit(0 if result.status == "passed" else 1)


if __name__ == "__main__":
    main()
