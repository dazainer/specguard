"""Versioned generation and report contracts, separate from manual QA schemas."""

import math
import statistics
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.evaluation.manifest import CommitSHA, GenerationConfig, SHA256, StrictModel
from app.evaluation.paths import RelativePath


class GeneratedTestFile(StrictModel):
    path: RelativePath
    content: str = Field(min_length=1, max_length=262144)


class ExecutableTestGenerationResult(StrictModel):
    files: list[GeneratedTestFile] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    targeted_requirements: list[str] = Field(default_factory=list, max_length=100)


class ArtifactRecord(StrictModel):
    path: RelativePath
    sha256: SHA256
    size_bytes: int = Field(ge=1)


class GenerationMetrics(StrictModel):
    attempts: int = Field(default=0, ge=0)
    successful: bool | None = None
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class BaselineRun(StrictModel):
    status: Literal["passed", "failed", "collection_error", "timeout", "resource_limit", "infrastructure_error"]
    collected_tests: int | None = Field(default=None, ge=0)
    passed_tests: int | None = Field(default=None, ge=0)
    failed_tests: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)


class MutationSummary(StrictModel):
    inventory_sha256: SHA256
    configuration_sha256: SHA256
    generated: int = Field(ge=0)
    killed: int = Field(ge=0)
    survived: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    invalid: int = Field(ge=0)
    errors: int = Field(ge=0)
    suspicious: int = Field(ge=0)
    denominator: int = Field(ge=0)
    score: float | None = Field(ge=0, le=1)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def honest_score(self):
        if self.generated != sum((self.killed, self.survived, self.timed_out, self.invalid, self.errors, self.suspicious)):
            raise ValueError("mutation outcome counts must sum to mutants generated")
        if self.denominator != self.killed + self.survived:
            raise ValueError("mutation denominator must be killed + survived")
        if self.denominator == 0:
            if self.score is not None:
                raise ValueError("mutation score is null when denominator is zero")
        elif self.score is None or not math.isclose(self.score, self.killed / self.denominator, abs_tol=1e-9):
            raise ValueError("mutation score must equal killed / (killed + survived)")
        return self


class SuiteReport(StrictModel):
    collection_status: Literal["not_run", "passed", "failed"] = "not_run"
    collected_tests: int | None = Field(default=None, ge=0)
    accepted_tests: int | None = Field(default=None, ge=0)
    rejected_tests: int | None = Field(default=None, ge=0)
    baseline_runs: list[BaselineRun] = Field(default_factory=list)
    baseline_pass_rate: float | None = Field(default=None, ge=0, le=1)
    repeat_duration_variance_seconds2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mutation: MutationSummary | None = None

    @model_validator(mode="after")
    def consistent_repeat_metrics(self):
        if self.collected_tests is not None and self.accepted_tests is not None and self.rejected_tests is not None:
            if self.accepted_tests + self.rejected_tests != self.collected_tests:
                raise ValueError("accepted/rejected counts must sum to collected tests")
        if not self.baseline_runs:
            if self.baseline_pass_rate is not None or self.repeat_duration_variance_seconds2 is not None:
                raise ValueError("unmeasured baseline metrics must be null")
        else:
            rate = sum(run.status == "passed" for run in self.baseline_runs) / len(self.baseline_runs)
            variance = statistics.pvariance(run.duration_seconds for run in self.baseline_runs)
            if self.baseline_pass_rate is None or not math.isclose(self.baseline_pass_rate, rate):
                raise ValueError("baseline pass rate must match repeat outcomes")
            if self.repeat_duration_variance_seconds2 is None or not math.isclose(self.repeat_duration_variance_seconds2, variance, abs_tol=1e-9):
                raise ValueError("repeat duration variance must match measured durations")
        return self


class Provenance(StrictModel):
    repository_commit: CommitSHA
    manifest_sha256: SHA256
    specification_sha256: SHA256
    context_sha256: SHA256
    dependency_lock_sha256: SHA256
    python_version: str
    runner_image_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    tool_versions: dict[str, str] = Field(default_factory=dict)


class EvaluationReport(StrictModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=128)
    status: Literal["prepared", "generating", "collecting", "baseline_running", "mutating", "completed", "failed", "cancelled"]
    context_mode: Literal["spec_only", "spec_plus_code"]
    generation_config: GenerationConfig
    provenance: Provenance
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    generation: GenerationMetrics = Field(default_factory=GenerationMetrics)
    native: SuiteReport = Field(default_factory=SuiteReport)
    generated: SuiteReport = Field(default_factory=SuiteReport)
    required_baseline_repeats: int = Field(ge=2, le=10)
    failure_reason: str | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def mutation_gate(self):
        if self.status == "prepared" and (
            self.generation.attempts != 0 or self.generation.successful is not None
            or any(suite.collection_status != "not_run" or suite.baseline_runs or suite.mutation is not None for suite in (self.native, self.generated))
        ):
            raise ValueError("prepared reports cannot claim generation or execution outcomes")
        for suite in (self.native, self.generated):
            if (suite.collection_status != "not_run" or suite.baseline_runs) and not self.provenance.runner_image_digest:
                raise ValueError("execution observations require a recorded runner image digest")
            if suite.mutation is not None:
                if suite.collection_status != "passed" or not suite.collected_tests:
                    raise ValueError("mutation requires successful nonempty collection")
                if len(suite.baseline_runs) < self.required_baseline_repeats or any(run.status != "passed" for run in suite.baseline_runs):
                    raise ValueError("mutation requires stable passing original-code baselines")
                if any(run.collected_tests != suite.collected_tests or run.passed_tests != suite.collected_tests or run.failed_tests != 0 for run in suite.baseline_runs):
                    raise ValueError("mutation requires all collected tests to pass consistently")
                if not self.provenance.runner_image_digest:
                    raise ValueError("mutation requires a recorded runner image digest")
                if suite.accepted_tests != suite.collected_tests or suite.rejected_tests != 0:
                    raise ValueError("mutation requires an accepted whole suite")
        if self.native.mutation and self.generated.mutation:
            if self.native.mutation.inventory_sha256 != self.generated.mutation.inventory_sha256:
                raise ValueError("native/generated mutation comparisons require the same inventory")
            if self.native.mutation.configuration_sha256 != self.generated.mutation.configuration_sha256:
                raise ValueError("native/generated mutation comparisons require the same configuration")
        return self
