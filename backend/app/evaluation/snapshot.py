"""Export a pinned local Git bundle without checkout hooks or importing target code."""

import os
import subprocess
import tempfile
from pathlib import Path

from app.evaluation.paths import safe_path, validate_relative_path

MAX_SNAPSHOT_FILES = 256
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024


def git(*args: str, cwd: Path) -> bytes:
    # Avoid host Git configuration, credential helpers, and interactive prompts.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=" + os.devnull, *args],
            cwd=cwd, env=env, capture_output=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("cannot read pinned Git bundle (Git required; bundle/commit must be valid)") from error
    return result.stdout


def export_bundle(bundle: Path, commit: str, destination: Path) -> dict[str, str]:
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("bundle must be a regular file no larger than 4 MiB")
    if destination.exists():
        raise ValueError("snapshot destination already exists")
    inventory = {}
    with tempfile.TemporaryDirectory(prefix="specguard-git-") as directory:
        repository = Path(directory)
        git("init", "--bare", "--template=", ".", cwd=repository)
        git("bundle", "verify", str(bundle.resolve()), cwd=repository)
        git("fetch", "--no-tags", str(bundle.resolve()), "refs/heads/main", cwd=repository)
        if git("cat-file", "-t", commit, cwd=repository).strip() != b"commit":
            raise ValueError("pinned revision is not a commit")
        entries = git("ls-tree", "-rz", "--full-tree", commit, cwd=repository).split(b"\0")
        if len(entries) - 1 > MAX_SNAPSHOT_FILES:
            raise ValueError("snapshot has too many files")
        files = []
        total = 0
        seen = set()
        for entry in filter(None, entries):
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split()
            path = validate_relative_path(raw_path.decode("utf-8"))
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("snapshot cannot contain symlinks, submodules, or special files")
            if path.casefold() in seen:
                raise ValueError("snapshot contains case-colliding paths")
            seen.add(path.casefold())
            size = int(git("cat-file", "-s", object_id, cwd=repository))
            total += size
            if total > MAX_SNAPSHOT_BYTES:
                raise ValueError("snapshot exceeds 4 MiB")
            data = git("cat-file", "blob", object_id, cwd=repository)
            files.append((path, data))
            inventory[path] = object_id
        # All entries are validated before writing an export. No .git is retained.
        destination.mkdir(parents=True)
        for path, data in files:
            output = safe_path(destination, path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
    return inventory
