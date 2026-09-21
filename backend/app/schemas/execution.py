"""Typed boundary for the local container runner; no arbitrary Docker options."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.evaluation.manifest import ResourceLimits, StrictModel, Tests
from app.evaluation.paths import RelativePath, overlap


class ExecutionRequest(StrictModel):
    target_snapshot: Path
    test_workspace: Path
    source_paths: list[RelativePath] = Field(default_factory=list, max_length=32)
    test_paths: list[RelativePath] = Field(min_length=1, max_length=32)
    command: list[str] = Field(default_factory=lambda: ["python", "-m", "pytest", "-q"])
    mode: Literal["collect", "run", "inventory"] = "run"
    mutation_paths: list[RelativePath] = Field(default_factory=list, max_length=32)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)

    @field_validator("command")
    @classmethod
    def pytest_only(cls, value):
        return Tests.pytest_command(value)

    @model_validator(mode="after")
    def separate_selections(self):
        if (self.mode == 'inventory') != bool(self.mutation_paths):
            raise ValueError('inventory mode requires mutation paths; pytest modes forbid them')
        if any(not any(path == source or path.startswith(source + '/') for source in self.source_paths) for path in self.mutation_paths):
            raise ValueError('mutation paths must be within selected source')
        for paths in (self.source_paths, self.test_paths):
            if any(overlap(left.casefold(), right.casefold()) for i, left in enumerate(paths) for right in paths[i + 1:]):
                raise ValueError("selected paths must not overlap or duplicate each other")
        if self.target_snapshot.resolve() == self.test_workspace.resolve():
            if any(overlap(source.casefold(), test.casefold()) for source in self.source_paths for test in self.test_paths):
                raise ValueError("source selection must not include the selected test suite")
        return self


class ExecutionResult(StrictModel):
    status: Literal["passed", "failed", "collection_error", "timeout", "resource_limit", "infrastructure_error"]
    exit_code: int | None = None
    duration_seconds: float = Field(ge=0)
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    output_bytes_seen: int = Field(default=0, ge=0)
    image_digest: str | None = None
    container_name: str
    oom_killed: bool = False
    cleanup_succeeded: bool = True
    error_message: str | None = None
    runtime: dict[str, str] = Field(default_factory=dict)
