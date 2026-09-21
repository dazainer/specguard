"""Trusted in-image launcher. Never run target/test code from the host."""

import json
import os
from pathlib import Path
import sys


class Observations:
    def __init__(self):
        self.counts = dict(collected=0, passed=0, failed=0, skipped=0, errors=0, failing_tests=[])

    def pytest_collection_finish(self, session):
        self.counts["collected"] = len(session.items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.counts["errors"] += 1

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.counts["skipped"] += 1
        elif report.failed:
            self.counts["failed" if report.when == "call" else "errors"] += 1
            if len(self.counts['failing_tests']) < 50:
                self.counts['failing_tests'].append(report.nodeid)
        elif report.when == "call" and report.passed:
            if hasattr(report, "wasxfail"):
                self.counts["skipped"] += 1
            else:
                self.counts["passed"] += 1


def main():
    if os.getuid() != 65532 or not Path("/.dockerenv").is_file():
        raise SystemExit("This launcher must run inside the non-root SpecGuard container")
    if len(sys.argv) < 4 or sys.argv[1] not in {"collect", "run"}:
        raise SystemExit(4)
    flags = json.loads(sys.argv[2])
    if not isinstance(flags, list) or any(flag not in {"-q", "-v", "--strict-markers", "--strict-config"} for flag in flags):
        raise SystemExit(4)
    paths = sys.argv[3:]
    if any(not Path(path).resolve().is_relative_to("/tests") for path in paths):
        raise SystemExit(4)
    os.umask(0o077)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ.pop("PYTEST_PLUGINS", None)
    import pytest

    # pytest is imported from the pinned image before exposing selected target code.
    sys.path.insert(0, "/target")
    arguments = [
        "-c", "/opt/specguard/pytest.ini", "--rootdir=/tests", "--noconftest",
        "--import-mode=importlib", "--basetemp=/scratch/pytest", "-p", "no:cacheprovider",
        "--color=no", "-s", *flags,
    ]
    if sys.argv[1] == "collect":
        arguments.append("--collect-only")
    observations = Observations()
    code = pytest.main([*arguments, *paths], plugins=[observations])
    print("\nSPECGUARD_PYTEST_JSON=" + json.dumps(observations.counts), flush=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
