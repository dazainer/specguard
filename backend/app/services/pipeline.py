"""
AI Pipeline Orchestrator

Runs the multi-stage test generation pipeline:
  Stage 1: Parse document (already done at upload)
  Stage 2: Extract requirements via AI
  Stage 3: Generate test cases per requirement via AI
  Stage 4: Validate, score, and persist

Each stage has independent validation. Failures at one stage
don't corrupt data from previous stages.
"""

import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.models import Document, Requirement, TestSuite, TestCase
from app.services.ai_client import AIClient, AIClientError
from app.services.scorer import compute_coverage_score
from app.schemas.ai_output import RequirementExtractionResult, TestGenerationResult
from app.prompts.templates import (
    REQUIREMENT_EXTRACTION_SYSTEM,
    REQUIREMENT_EXTRACTION_USER,
    TEST_GENERATION_SYSTEM,
    TEST_GENERATION_USER,
)

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


async def run_pipeline(
    db: AsyncSession,
    document_id: str,
    test_suite_id: str,
) -> None:
    """
    Run the full test generation pipeline for a document.

    This is called as a background task. It updates the test_suite
    status as it progresses.
    """
    start_time = time.time()
    ai = AIClient()

    # Load document
    doc = await db.get(Document, document_id)
    if not doc:
        raise PipelineError(f"Document {document_id} not found")

    suite = await db.get(TestSuite, test_suite_id)
    if not suite:
        raise PipelineError(f"TestSuite {test_suite_id} not found")

    # Load project name for context (explicit query — async SQLAlchemy can't lazy-load)
    from app.models.models import Project
    project = await db.get(Project, doc.project_id)
    project_name = project.name if project else "Unknown Project"

    try:
        # ─── Stage 2: Extract Requirements ───
        logger.info(f"Stage 2: Extracting requirements from document {document_id}")

        extraction_result = await ai.generate_structured(
            system_prompt=REQUIREMENT_EXTRACTION_SYSTEM,
            user_prompt=REQUIREMENT_EXTRACTION_USER.format(document_text=doc.raw_text),
            output_schema=RequirementExtractionResult,
        )

        # Clear old requirements for this document (if regenerating)
        old_reqs = await db.execute(
            select(Requirement).where(Requirement.document_id == document_id)
        )
        for old_req in old_reqs.scalars().all():
            await db.delete(old_req)

        # Persist new requirements
        requirements: list[Requirement] = []
        for idx, req_data in enumerate(extraction_result.requirements):
            req = Requirement(
                document_id=document_id,
                requirement_text=req_data.requirement_text,
                category=req_data.category,
                priority=req_data.priority,
                order_index=idx,
            )
            db.add(req)
            requirements.append(req)

        await db.flush()  # Assign IDs

        logger.info(f"Extracted {len(requirements)} requirements")

        # ─── Stage 3: Generate Test Cases ───
        logger.info(f"Stage 3: Generating test cases for {len(requirements)} requirements")

        all_test_cases: list[TestCase] = []
        requirement_ids_with_tests: set[str] = set()

        for req in requirements:
            try:
                gen_result = await ai.generate_structured(
                    system_prompt=TEST_GENERATION_SYSTEM,
                    user_prompt=TEST_GENERATION_USER.format(
                        requirement_text=req.requirement_text,
                        category=req.category,
                        project_name=project_name,
                    ),
                    output_schema=TestGenerationResult,
                )

                for tc_data in gen_result.test_cases:
                    tc = TestCase(
                        test_suite_id=test_suite_id,
                        requirement_id=req.id,
                        title=tc_data.title,
                        description=tc_data.description,
                        test_type=tc_data.test_type,
                        preconditions=tc_data.preconditions,
                        steps=tc_data.steps,
                        expected_result=tc_data.expected_result,
                        priority=tc_data.priority,
                        tags=tc_data.tags,
                    )
                    db.add(tc)
                    all_test_cases.append(tc)

                requirement_ids_with_tests.add(req.id)

            except AIClientError as e:
                # Log but continue — partial results are better than none
                logger.warning(f"Failed to generate tests for requirement {req.id}: {e}")

        await db.flush()

        logger.info(f"Generated {len(all_test_cases)} test cases total")

        # ─── Stage 4: Score and Finalize ───
        logger.info("Stage 4: Computing coverage score")

        tc_dicts = [
            {"test_type": tc.test_type, "steps": tc.steps, "priority": tc.priority}
            for tc in all_test_cases
        ]

        scores = compute_coverage_score(
            total_requirements=len(requirements),
            test_cases=tc_dicts,
            requirement_ids_with_tests=requirement_ids_with_tests,
        )

        elapsed = round(time.time() - start_time, 2)

        suite.status = "completed"
        suite.coverage_score = scores["overall"]
        suite.score_breakdown = scores
        suite.metadata_ = {
            "total_requirements": len(requirements),
            "total_test_cases": len(all_test_cases),
            "generation_time_seconds": elapsed,
            "model": ai.model,
        }

        await db.commit()
        logger.info(f"Pipeline completed in {elapsed}s — score: {scores['overall']}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        suite.status = "failed"
        suite.error_message = str(e)
        await db.commit()
        raise
