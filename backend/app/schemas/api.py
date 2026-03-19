from pydantic import BaseModel, Field
from datetime import datetime


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    total_test_cases: int = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    document_count: int = 0


# ──────────────────────────────────────────────
# Document
# ──────────────────────────────────────────────
class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    raw_text: str
    uploaded_at: datetime
    requirement_count: int = 0
    test_suite_count: int = 0

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    uploaded_at: datetime
    requirement_count: int = 0


# ──────────────────────────────────────────────
# Requirement
# ──────────────────────────────────────────────
class RequirementResponse(BaseModel):
    id: str
    requirement_text: str
    category: str
    priority: str
    order_index: int

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Test Suite
# ──────────────────────────────────────────────
class TestSuiteListResponse(BaseModel):
    id: str
    version: int
    status: str
    coverage_score: float | None
    created_at: datetime
    test_case_count: int = 0


class TestSuiteResponse(BaseModel):
    id: str
    document_id: str
    version: int
    status: str
    coverage_score: float | None
    score_breakdown: dict | None
    metadata_: dict | None = Field(None, alias="metadata_")
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ──────────────────────────────────────────────
# Test Case
# ──────────────────────────────────────────────
class TestCaseResponse(BaseModel):
    id: str
    test_suite_id: str
    requirement_id: str | None
    title: str
    description: str
    test_type: str
    preconditions: str
    steps: list[str]
    expected_result: str
    priority: str
    status: str
    tags: list[str]

    model_config = {"from_attributes": True}


class TestCaseUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(generated|approved|rejected|edited)$")
    title: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    priority: str | None = None


# ──────────────────────────────────────────────
# Generation Status
# ──────────────────────────────────────────────
class GenerationStartResponse(BaseModel):
    test_suite_id: str
    status: str
    message: str


class GenerationStatusResponse(BaseModel):
    test_suite_id: str
    status: str
    coverage_score: float | None = None
    test_case_count: int = 0
    error_message: str | None = None


# ──────────────────────────────────────────────
# Dashboard / Stats
# ──────────────────────────────────────────────
class ProjectStatsResponse(BaseModel):
    project_id: str
    project_name: str
    total_documents: int
    total_requirements: int
    total_test_suites: int
    total_test_cases: int
    avg_coverage_score: float | None
    test_type_breakdown: dict[str, int]
    status_breakdown: dict[str, int]
    recent_generations: list[TestSuiteListResponse]
