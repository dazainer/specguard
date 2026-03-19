"""Tests for the coverage scoring service."""

from app.services.scorer import compute_coverage_score


class TestCoverageScoring:
    def test_perfect_coverage(self):
        test_cases = [
            {"test_type": "functional", "steps": ["s1", "s2"], "priority": "high"},
            {"test_type": "edge_case", "steps": ["s1", "s2"], "priority": "medium"},
            {"test_type": "negative", "steps": ["s1", "s2"], "priority": "medium"},
        ]
        scores = compute_coverage_score(
            total_requirements=1,
            test_cases=test_cases,
            requirement_ids_with_tests={"req-1"},
        )
        assert scores["requirement_coverage"] == 1.0
        assert scores["edge_case_ratio"] > 0
        assert scores["negative_test_ratio"] > 0
        assert scores["step_completeness"] == 1.0
        assert 0.0 <= scores["overall"] <= 1.0

    def test_empty_test_cases(self):
        scores = compute_coverage_score(
            total_requirements=5,
            test_cases=[],
            requirement_ids_with_tests=set(),
        )
        assert scores["overall"] == 0.0
        assert scores["total_test_cases"] == 0

    def test_partial_coverage(self):
        test_cases = [
            {"test_type": "functional", "steps": ["s1", "s2"], "priority": "high"},
            {"test_type": "functional", "steps": ["s1"], "priority": "medium"},
        ]
        scores = compute_coverage_score(
            total_requirements=4,
            test_cases=test_cases,
            requirement_ids_with_tests={"req-1"},
        )
        # Only 1 of 4 requirements covered
        assert scores["requirement_coverage"] == 0.25
        # No edge or negative tests
        assert scores["edge_case_ratio"] == 0.0
        assert scores["negative_test_ratio"] == 0.0

    def test_step_completeness_calculation(self):
        test_cases = [
            {"test_type": "functional", "steps": ["s1", "s2", "s3"], "priority": "high"},
            {"test_type": "functional", "steps": ["s1"], "priority": "high"},  # only 1 step
            {"test_type": "edge_case", "steps": ["s1", "s2"], "priority": "medium"},
        ]
        scores = compute_coverage_score(
            total_requirements=1,
            test_cases=test_cases,
            requirement_ids_with_tests={"req-1"},
        )
        # 2 of 3 have >= 2 steps
        assert abs(scores["step_completeness"] - 0.667) < 0.01

    def test_score_capped_at_one(self):
        """Score should never exceed 1.0 even with extreme values."""
        test_cases = [
            {"test_type": "edge_case", "steps": ["s1", "s2"], "priority": "high"},
            {"test_type": "negative", "steps": ["s1", "s2"], "priority": "high"},
        ]
        scores = compute_coverage_score(
            total_requirements=1,
            test_cases=test_cases,
            requirement_ids_with_tests={"req-1"},
        )
        assert scores["overall"] <= 1.0
