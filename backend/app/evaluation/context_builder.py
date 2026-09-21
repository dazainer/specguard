"""Build model-visible context from declared files only, without importing code."""

import hashlib
import json
from pathlib import Path

from app.evaluation.manifest import Manifest
from app.evaluation.paths import safe_path

MAX_CONTEXT_BYTES = 262144


def read_text(root: Path, relative: str) -> str:
    path = safe_path(root, relative, must_exist=True)
    if not path.is_file():
        raise ValueError(f"expected a regular file: {relative}")
    with path.open("rb") as file:
        data = file.read(MAX_CONTEXT_BYTES + 1)
    if len(data) > MAX_CONTEXT_BYTES:
        raise ValueError(f"context file too large: {relative}")
    return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def canonical_json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_context(manifest: Manifest, subject_root: Path, snapshot: Path) -> dict:
    context = {
        "mode": manifest.context.mode,
        "specification": read_text(subject_root, manifest.specification.path),
        "public_interface": read_text(subject_root, manifest.context.interface_path),
        "source_files": {
            path: read_text(snapshot, path) for path in manifest.context.source_files
        },
    }
    if len(canonical_json(context)) > MAX_CONTEXT_BYTES:
        raise ValueError("combined context exceeds 256 KiB")
    return context
