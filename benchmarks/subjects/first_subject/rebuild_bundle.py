"""Rebuild the deterministic first-party Git bundle without executing target code.

Only a temporary Git object database is written; this never commits to the
SpecGuard repository. Keep the resulting commit pinned in specguard.yaml.
"""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def rebuild(root=ROOT, title="Reservation pricing benchmark v1"):
    with tempfile.TemporaryDirectory(prefix="specguard-benchmark-") as directory:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        }

        def git(*args, data=None):
            return subprocess.run(
                ["git", *args], cwd=directory, env=env, input=data,
                check=True, capture_output=True, timeout=30,
            ).stdout.strip().decode()

        git("init", "--bare", "--object-format=sha1", "--template=", ".")
        for path in sorted((root / "target").rglob("*")):
            if path.is_symlink():
                raise ValueError("benchmark target cannot contain symlinks")
            if not path.is_file():
                continue
            relative = path.relative_to(root / "target").as_posix()
            if any(part.startswith(".") or part == "__pycache__" for part in Path(relative).parts):
                raise ValueError("unexpected hidden file/cache in benchmark target")
            blob = git("hash-object", "-w", "--stdin", data=path.read_bytes())
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}")
        tree = git("write-tree")
        commit_data = (
            f"tree {tree}\n"
            "author SpecGuard Benchmark <benchmark@specguard.invalid> 1700000000 +0000\n"
            "committer SpecGuard Benchmark <benchmark@specguard.invalid> 1700000000 +0000\n"
            f"\n{title}\n"
        ).encode()
        commit = git("hash-object", "-t", "commit", "-w", "--stdin", data=commit_data)
        git("update-ref", "refs/heads/main", commit)
        git("bundle", "create", str(root / "target.bundle"), "refs/heads/main")
        print(commit)
        return commit


if __name__ == "__main__":
    rebuild()
