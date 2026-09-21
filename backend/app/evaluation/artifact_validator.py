"""Validate generated artifacts as data. AST parsing never executes their code."""

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.evaluation.context_builder import sha256
from app.evaluation.manifest import Manifest
from app.evaluation.paths import beneath, safe_path
from app.schemas.evaluation import ExecutableTestGenerationResult


@dataclass(frozen=True)
class ValidatedArtifact:
    path: str
    content: str
    sha256: str
    size_bytes: int


def validate_artifacts(
    result: ExecutableTestGenerationResult,
    manifest: Manifest,
    workspace: Path | None = None,
) -> list[ValidatedArtifact]:
    limits = manifest.artifacts
    if len(result.files) > limits.max_files:
        raise ValueError("too many generated files")
    artifacts = []
    seen = set()
    total = 0
    for file in result.files:
        name = PurePosixPath(file.path).name
        if not beneath(file.path, manifest.tests.generated_path):
            raise ValueError("artifact must be beneath the configured generated directory")
        if not name.startswith("test_") or not name.endswith(".py"):
            raise ValueError("only test_*.py generated artifacts are permitted")
        if file.path.casefold() in seen:
            raise ValueError("duplicate or case-colliding artifact path")
        seen.add(file.path.casefold())
        if workspace is not None:
            path = safe_path(workspace, file.path)
            if path.exists():
                raise ValueError("generated artifact must not overwrite an existing file")
        content = file.content.replace("\r\n", "\n").replace("\r", "\n")
        raw = content.encode("utf-8")
        if len(raw) > limits.max_file_bytes:
            raise ValueError("generated file exceeds byte limit")
        total += len(raw)
        if total > limits.max_total_bytes:
            raise ValueError("generated artifacts exceed total byte limit")
        try:
            ast.parse(content, filename=file.path)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
            raise ValueError(f"invalid Python syntax in {file.path}") from error
        artifacts.append(ValidatedArtifact(file.path, content, sha256(raw), len(raw)))
    return artifacts
