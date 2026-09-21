"""Portable path policy shared by manifests, snapshots, and generated artifacts."""

import re
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator


def validate_relative_path(value: str) -> str:
    if not value or len(value) > 240:
        raise ValueError("path must contain 1–240 characters")
    parts = value.split("/")
    if any(
        part in {"", ".", "..", ".git", ".env"}
        or part.startswith(".env.")
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        for part in parts
    ):
        raise ValueError("use a normalized relative POSIX path without traversal, secrets, or .git")
    return value


RelativePath = Annotated[str, AfterValidator(validate_relative_path)]


def beneath(path: str, directory: str) -> bool:
    return path.startswith(directory + "/")


def overlap(left: str, right: str) -> bool:
    return left == right or beneath(left, right) or beneath(right, left)


def safe_path(root: Path, relative: str, *, must_exist: bool = False) -> Path:
    """Reject all symlink components, even links that currently stay inside root.

    This is preflight validation for private, immutable preparation workspaces,
    not a race-proof boundary for concurrently modified hostile directories.
    """
    validate_relative_path(relative)
    root = root.resolve(strict=True)
    candidate = root
    for part in relative.split("/"):
        candidate /= part
        if candidate.is_symlink():
            raise ValueError(f"symlinks are not permitted: {relative}")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("path escapes its workspace")
    if must_exist and not candidate.exists():
        raise ValueError(f"required path does not exist: {relative}")
    return candidate
