"""Parse explicit runner observations, not human-oriented pytest summaries."""
import json

from pydantic import Field

from app.evaluation.manifest import StrictModel


class PytestObservation(StrictModel):
    collected: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(ge=0)
    failing_tests: list[str] = Field(default_factory=list, max_length=50)


def observe(result):
    if result.output_truncated:
        return None
    lines = [line.removeprefix('SPECGUARD_PYTEST_JSON=') for line in result.stdout.splitlines()
             if line.startswith('SPECGUARD_PYTEST_JSON=')]
    if len(lines) != 1:
        return None
    try:
        return PytestObservation.model_validate(json.loads(lines[0]))
    except ValueError:
        return None


def all_passed(result, count):
    observed = observe(result)
    return (result.status == 'passed' and observed is not None and count > 0
            and observed.collected == observed.passed == count
            and observed.failed == observed.skipped == observed.errors == 0)
