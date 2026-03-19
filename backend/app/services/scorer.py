"""
Coverage Scoring Service

Computes heuristic quality scores for generated test suites.
This gives you a reliability metric to discuss in interviews.
"""


def compute_coverage_score(
    total_requirements: int,
    test_cases: list[dict],
    requirement_ids_with_tests: set[str],
) -> dict:
    """
    Compute a coverage score for a test suite.

    Args:
        total_requirements: Total number of extracted requirements
        test_cases: List of test case dicts with 'test_type', 'steps', 'priority'
        requirement_ids_with_tests: Set of requirement IDs that have at least one test

    Returns:
        Dict with score breakdown and overall score (0.0 - 1.0)
    """
    if not test_cases or total_requirements == 0:
        return {
            "overall": 0.0,
            "requirement_coverage": 0.0,
            "edge_case_ratio": 0.0,
            "negative_test_ratio": 0.0,
            "step_completeness": 0.0,
            "total_test_cases": len(test_cases),
            "total_requirements": total_requirements,
        }

    n_tests = len(test_cases)

    # 1. Requirement coverage: % of requirements with at least one test
    requirement_coverage = len(requirement_ids_with_tests) / total_requirements

    # 2. Edge case density: % of tests that are edge cases (target: ~20-30%)
    edge_count = sum(1 for tc in test_cases if tc.get("test_type") == "edge_case")
    edge_case_ratio = edge_count / n_tests

    # 3. Negative test density: % of tests that are negative (target: ~15-25%)
    negative_count = sum(1 for tc in test_cases if tc.get("test_type") == "negative")
    negative_test_ratio = negative_count / n_tests

    # 4. Step completeness: % of test cases with >= 2 steps
    complete_count = sum(1 for tc in test_cases if len(tc.get("steps", [])) >= 2)
    step_completeness = complete_count / n_tests

    # Weighted composite score
    overall = (
        requirement_coverage * 0.40
        + edge_case_ratio * 0.20
        + negative_test_ratio * 0.20
        + step_completeness * 0.20
    )

    # Cap at 1.0
    overall = min(overall, 1.0)

    return {
        "overall": round(overall, 3),
        "requirement_coverage": round(requirement_coverage, 3),
        "edge_case_ratio": round(edge_case_ratio, 3),
        "negative_test_ratio": round(negative_test_ratio, 3),
        "step_completeness": round(step_completeness, 3),
        "total_test_cases": n_tests,
        "total_requirements": total_requirements,
        "edge_case_count": edge_count,
        "negative_test_count": negative_count,
    }
