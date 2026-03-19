"""
Tests for AI output validation schemas.

These prove the reliability layer works — invalid AI outputs
get rejected, valid ones pass through.
"""

import pytest
from pydantic import ValidationError
from app.schemas.ai_output import (
    ExtractedRequirement,
    RequirementExtractionResult,
    GeneratedTestCase,
    TestGenerationResult,
)


# ──────────────────────────────────────────────
# Requirement Extraction Schema Tests
# ──────────────────────────────────────────────
class TestExtractedRequirement:
    def test_valid_requirement(self):
        req = ExtractedRequirement(
            requirement_text="Users should be able to log in with email and password",
            category="functional",
            priority="high",
        )
        assert req.requirement_text == "Users should be able to log in with email and password"
        assert req.category == "functional"
        assert req.priority == "high"

    def test_rejects_short_text(self):
        with pytest.raises(ValidationError) as exc_info:
            ExtractedRequirement(
                requirement_text="Login",
                category="functional",
                priority="high",
            )
        assert "min_length" in str(exc_info.value) or "at least" in str(exc_info.value).lower()

    def test_rejects_invalid_category(self):
        with pytest.raises(ValidationError):
            ExtractedRequirement(
                requirement_text="Users should be able to log in with email and password",
                category="banana",
                priority="high",
            )

    def test_rejects_invalid_priority(self):
        with pytest.raises(ValidationError):
            ExtractedRequirement(
                requirement_text="Users should be able to log in with email and password",
                category="functional",
                priority="super-high",
            )

    def test_rejects_vague_requirement(self):
        with pytest.raises(ValidationError):
            ExtractedRequirement(
                requirement_text="The system should handle various things etc",
                category="functional",
                priority="low",
            )

    def test_all_categories_accepted(self):
        for cat in ["functional", "ui", "api", "security", "performance", "data"]:
            req = ExtractedRequirement(
                requirement_text="A sufficiently long requirement for testing purposes",
                category=cat,
                priority="medium",
            )
            assert req.category == cat


class TestRequirementExtractionResult:
    def test_valid_result(self):
        result = RequirementExtractionResult(
            requirements=[
                {
                    "requirement_text": "Users must register with a valid email address",
                    "category": "functional",
                    "priority": "high",
                }
            ]
        )
        assert len(result.requirements) == 1

    def test_rejects_empty_list(self):
        with pytest.raises(ValidationError):
            RequirementExtractionResult(requirements=[])

    def test_multiple_requirements(self):
        result = RequirementExtractionResult(
            requirements=[
                {"requirement_text": "User can log in with credentials", "category": "functional", "priority": "high"},
                {"requirement_text": "API returns 401 for invalid tokens", "category": "api", "priority": "high"},
                {"requirement_text": "Dashboard loads in under 3 seconds", "category": "performance", "priority": "medium"},
            ]
        )
        assert len(result.requirements) == 3


# ──────────────────────────────────────────────
# Test Case Generation Schema Tests
# ──────────────────────────────────────────────
class TestGeneratedTestCase:
    def test_valid_test_case(self):
        tc = GeneratedTestCase(
            title="Verify login with valid credentials",
            description="Test that a user can log in with correct email and password",
            test_type="functional",
            preconditions="User has a registered account",
            steps=["Navigate to login page", "Enter valid email", "Enter valid password", "Click submit"],
            expected_result="User is redirected to dashboard and session is created",
            priority="critical",
            tags=["auth", "login", "smoke"],
        )
        assert tc.test_type == "functional"
        assert len(tc.steps) == 4
        assert tc.tags == ["auth", "login", "smoke"]

    def test_rejects_short_title(self):
        with pytest.raises(ValidationError):
            GeneratedTestCase(
                title="Test",
                description="A valid description for testing",
                test_type="functional",
                steps=["Step 1"],
                expected_result="Some expected result here",
                priority="medium",
            )

    def test_rejects_empty_steps(self):
        with pytest.raises(ValidationError):
            GeneratedTestCase(
                title="Valid test case title here",
                description="A valid description for testing",
                test_type="functional",
                steps=[],
                expected_result="Some expected result here",
                priority="medium",
            )

    def test_rejects_blank_steps(self):
        with pytest.raises(ValidationError):
            GeneratedTestCase(
                title="Valid test case title here",
                description="A valid description for testing",
                test_type="functional",
                steps=["  ", ""],
                expected_result="Some expected result here",
                priority="medium",
            )

    def test_rejects_invalid_test_type(self):
        with pytest.raises(ValidationError):
            GeneratedTestCase(
                title="Valid test case title here",
                description="A valid description for testing",
                test_type="integration",
                steps=["Step 1"],
                expected_result="Some expected result here",
                priority="medium",
            )

    def test_tags_normalized_to_lowercase(self):
        tc = GeneratedTestCase(
            title="Verify input validation works",
            description="Test that invalid inputs are properly rejected",
            test_type="negative",
            steps=["Submit empty form"],
            expected_result="Error message is displayed to user",
            priority="high",
            tags=["Auth", "VALIDATION", "Input"],
        )
        assert tc.tags == ["auth", "validation", "input"]

    def test_default_preconditions(self):
        tc = GeneratedTestCase(
            title="Verify default behavior works",
            description="Test that the system handles defaults correctly",
            test_type="functional",
            steps=["Open the page"],
            expected_result="Default state is displayed correctly",
            priority="low",
        )
        assert tc.preconditions == "None"


class TestTestGenerationResult:
    def test_valid_result(self):
        result = TestGenerationResult(
            test_cases=[
                {
                    "title": "Test valid login flow",
                    "description": "Verify user can log in successfully",
                    "test_type": "functional",
                    "steps": ["Go to login", "Enter credentials", "Submit"],
                    "expected_result": "User sees dashboard after login",
                    "priority": "critical",
                    "tags": ["auth"],
                }
            ]
        )
        assert len(result.test_cases) == 1

    def test_rejects_empty_test_cases(self):
        with pytest.raises(ValidationError):
            TestGenerationResult(test_cases=[])
