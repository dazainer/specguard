"""Stage only explicitly selected input files; never mount caller directories."""

import os
import stat
from pathlib import Path

from app.evaluation.paths import safe_path, validate_relative_path

MAX_FILES = 256
MAX_BYTES = 4 * 1024 * 1024
SENSITIVE = {".aws", ".ssh", ".docker", ".kube", ".gnupg", ".git", ".env"}


def stage_selection(root: Path, selected: list[str], destination: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("input root must be an existing nonsymlink directory")
    root = root.resolve()
    destination.mkdir(mode=0o755)
    files = 0
    total = 0
    seen = set()

    def copy(relative: str):
        nonlocal files, total
        validate_relative_path(relative)
        if any(part.casefold() in SENSITIVE or part.casefold().startswith(".env.") for part in relative.split("/")):
            raise ValueError("sensitive input path is forbidden")
        if relative.casefold() in seen:
            raise ValueError("input paths collide")
        seen.add(relative.casefold())
        path = safe_path(root, relative, must_exist=True)
        info = path.lstat()
        target = destination / relative
        if stat.S_ISDIR(info.st_mode):
            target.mkdir(parents=True, exist_ok=True, mode=0o755)
            for child in sorted(path.iterdir()):
                copy(relative + "/" + child.name)
            return
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("only regular, non-hardlinked input files are allowed")
        files += 1
        total += info.st_size
        if files > MAX_FILES or total > MAX_BYTES:
            raise ValueError("staged inputs exceed file-count or byte limits")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            current = os.fstat(source.fileno())
            if (current.st_dev, current.st_ino, current.st_size, current.st_nlink) != (info.st_dev, info.st_ino, info.st_size, 1):
                raise ValueError("input changed during staging")
            data = source.read(info.st_size + 1)
        if len(data) != info.st_size:
            raise ValueError("input changed during staging")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        target.write_bytes(data)
        target.chmod(0o444)

    for relative in selected:
        copy(relative)
    # The private parent remains 0700; mounted subdirectories must be readable
    # by the container's numeric non-root UID even under a restrictive host umask.
    destination.chmod(0o755)
    for path in destination.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
