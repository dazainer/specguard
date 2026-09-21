import pytest
from pydantic import ValidationError

from app.schemas.evaluation import EvaluationReport, MutationSummary, Provenance


@pytest.fixture
def mutation():
    return dict(inventory_sha256="a" * 64, configuration_sha256="b" * 64, generated=10, killed=4, survived=2, timed_out=1,
                invalid=1, errors=1, suspicious=1, denominator=6, score=4 / 6, duration_seconds=1.0)


@pytest.fixture
def report(manifest):
    return EvaluationReport(
        run_id="fixture-run", status="prepared", context_mode="spec_plus_code",
        generation_config=manifest.generation, required_baseline_repeats=2,
        provenance=Provenance(
            repository_commit=manifest.repository.commit, manifest_sha256="a" * 64,
            specification_sha256="b" * 64, context_sha256="c" * 64,
            dependency_lock_sha256="d" * 64, python_version="3.12",
        ),
    )


def test_prepared_report_does_not_claim_execution(report):
    assert report.provenance.runner_image_digest is None
    assert report.generated.collected_tests is None
    assert report.generated.baseline_runs == []
    assert report.generated.mutation is None
    assert report.generation.attempts == 0
    assert report.generation.successful is None
    assert EvaluationReport.model_validate_json(report.model_dump_json()) == report


def test_mutation_score_excludes_timeout_invalid_and_errors(mutation):
    summary = MutationSummary.model_validate(mutation)
    assert summary.score == 4 / 6
    assert summary.denominator == 6
    assert MutationSummary.model_validate_json(summary.model_dump_json()) == summary


@pytest.mark.parametrize("field, value", [("denominator", 10), ("score", 0.8), ("generated", 9), ("killed", -1), ("score", None)])
def test_inconsistent_mutation_rejected(mutation, field, value):
    mutation[field] = value
    with pytest.raises(ValidationError):
        MutationSummary.model_validate(mutation)


def test_zero_denominator_has_null_score(mutation):
    mutation.update(killed=0, survived=0, generated=4, denominator=0, score=None)
    assert MutationSummary.model_validate(mutation).score is None
    mutation["score"] = 0.0
    with pytest.raises(ValidationError):
        MutationSummary.model_validate(mutation)


def eligible_report(report, mutation):
    data = report.model_dump()
    data["status"] = "completed"
    data["provenance"]["runner_image_digest"] = "sha256:" + "f" * 64
    suite = dict(collection_status="passed", collected_tests=2, accepted_tests=2, rejected_tests=0,
                 baseline_runs=[dict(status="passed", collected_tests=2, passed_tests=2, failed_tests=0, duration_seconds=0.1)] * 2,
                 baseline_pass_rate=1.0, repeat_duration_variance_seconds2=0.0,
                 mutation=mutation)
    data["generated"] = suite
    data["native"] = dict(suite)
    return data


def test_comparable_report_round_trip(report, mutation):
    parsed = EvaluationReport.model_validate(eligible_report(report, mutation))
    assert EvaluationReport.model_validate_json(parsed.model_dump_json()) == parsed


def test_prepared_report_cannot_claim_measurements(report, mutation):
    data = eligible_report(report, mutation)
    data["status"] = "prepared"
    with pytest.raises(ValidationError, match="prepared reports"):
        EvaluationReport.model_validate(data)


@pytest.mark.parametrize("failure", ["failed_baseline", "too_few_repeats", "no_collection", "empty_suite", "no_image", "different_inventory", "different_config", "changing_counts", "wrong_rate", "wrong_variance", "wrong_accepted_count"])
def test_report_rejects_ungated_or_unfair_mutation(report, mutation, failure):
    data = eligible_report(report, mutation)
    if failure == "failed_baseline":
        data["generated"]["baseline_runs"] = [dict(status="failed", duration_seconds=0.1)] * 2
    elif failure == "too_few_repeats":
        data["generated"]["baseline_runs"] = data["generated"]["baseline_runs"][:1]
    elif failure == "no_collection":
        data["generated"]["collection_status"] = "not_run"
    elif failure == "empty_suite":
        data["generated"]["collected_tests"] = 0
    elif failure == "no_image":
        data["provenance"]["runner_image_digest"] = None
    elif failure == "different_inventory":
        data["generated"]["mutation"] = dict(mutation, inventory_sha256="b" * 64)
    elif failure == "different_config":
        data["generated"]["mutation"] = dict(mutation, configuration_sha256="c" * 64)
    elif failure == "changing_counts":
        data["generated"]["baseline_runs"] = [dict(status="passed", collected_tests=1, passed_tests=1, failed_tests=0, duration_seconds=0.1)] * 2
    elif failure == "wrong_rate":
        data["generated"]["baseline_pass_rate"] = 0.5
    elif failure == "wrong_accepted_count":
        data["generated"]["accepted_tests"] = 10
    else:
        data["generated"]["repeat_duration_variance_seconds2"] = 5.0
    with pytest.raises(ValidationError):
        EvaluationReport.model_validate(data)
