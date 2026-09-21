import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import models
from app.services import pipeline
from app.services.ai_client import AIClientError


async def test_success_persists_tests_and_scores(db, seeded, fake_ai, extraction, generated):
    _, document_id, suite_id = seeded
    fake = fake_ai(extraction, generated, generated)
    assert (await db.get(models.TestSuite, suite_id)).status == "generating"
    await pipeline.run_pipeline(db, document_id, suite_id)
    suite = await db.get(models.TestSuite, suite_id)
    assert suite.status == "completed"
    assert suite.score_breakdown["requirement_coverage"] == 1
    assert suite.metadata_["failed_requirements"] == 0
    assert suite.metadata_["model"] == "deterministic-fake"
    assert len(fake.calls) == 3
    assert await db.scalar(select(func.count(models.TestCase.id))) == 2
    assert await db.scalar(select(func.count(models.Requirement.id))) == 2


async def test_partial_failure_keeps_successful_tests(db, seeded, fake_ai, extraction, generated):
    _, document_id, suite_id = seeded
    fake_ai(extraction, AIClientError("generation failed"), generated)
    await pipeline.run_pipeline(db, document_id, suite_id)
    suite = await db.get(models.TestSuite, suite_id)
    assert suite.status == "completed"
    assert suite.metadata_["total_test_cases"] == 1
    assert suite.metadata_["requirements_with_tests"] == 1
    assert suite.metadata_["failed_requirements"] == 1
    assert suite.score_breakdown["requirement_coverage"] == 0.5


@pytest.mark.parametrize("stage", ["extraction", "all_requirements"])
async def test_failure_is_persisted(db, seeded, fake_ai, extraction, stage):
    _, document_id, suite_id = seeded
    if stage == "extraction":
        fake_ai(AIClientError("extraction failed"))
        error = AIClientError
    else:
        fake_ai(extraction, AIClientError("failed"), AIClientError("failed"))
        error = pipeline.PipelineError
    with pytest.raises(error):
        await pipeline.run_pipeline(db, document_id, suite_id)
    suite = await db.get(models.TestSuite, suite_id)
    assert suite.status == "failed" and suite.error_message
    assert suite.coverage_score is None
    assert await db.scalar(select(func.count(models.TestCase.id))) == 0


async def test_client_initialization_failure_marks_suite_failed(db, seeded, monkeypatch):
    def broken_client():
        raise RuntimeError("client initialization failed")

    monkeypatch.setattr(pipeline, "AIClient", broken_client)
    with pytest.raises(RuntimeError):
        await pipeline.run_pipeline(db, seeded[1], seeded[2])
    assert (await db.get(models.TestSuite, seeded[2])).status == "failed"


async def test_database_failure_rolls_back_before_recording_failure(db, seeded, fake_ai, extraction, generated):
    old = models.Requirement(document_id=seeded[1], requirement_text="Existing requirement", category="functional", priority="high")
    db.add(old)
    await db.commit()
    old_id = old.id
    # Force a real database failure during test persistence, after requirement replacement.
    await db.execute(text("CREATE TRIGGER reject_test BEFORE INSERT ON test_cases BEGIN SELECT RAISE(ABORT, 'test fixture failure'); END"))
    await db.commit()
    fake_ai(extraction, generated, generated)
    with pytest.raises(IntegrityError):
        await pipeline.run_pipeline(db, seeded[1], seeded[2])
    assert (await db.get(models.TestSuite, seeded[2])).status == "failed"
    assert await db.get(models.Requirement, old_id) is not None
    assert await db.scalar(select(func.count(models.Requirement.id))) == 1


async def test_regeneration_preserves_old_suite_tests(db, seeded, fake_ai, extraction, generated):
    fake_ai(extraction, generated, generated)
    await pipeline.run_pipeline(db, seeded[1], seeded[2])
    next_suite = models.TestSuite(document_id=seeded[1], version=2)
    db.add(next_suite)
    await db.commit()
    fake_ai(extraction, generated, generated)
    await pipeline.run_pipeline(db, seeded[1], next_suite.id)
    assert await db.scalar(select(func.count(models.TestCase.id))) == 4
    assert await db.scalar(select(func.count(models.Requirement.id))) == 2
    assert (await db.get(models.TestSuite, seeded[2])).status == "completed"
