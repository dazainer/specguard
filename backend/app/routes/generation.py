import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db, async_session
from app.models.models import Document, TestSuite, TestCase, Requirement
from app.schemas.api import (
    GenerationStartResponse,
    GenerationStatusResponse,
    RequirementResponse,
)
from app.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


async def _run_pipeline_background(document_id: str, test_suite_id: str):
    """Run pipeline in a background task with its own DB session."""
    async with async_session() as db:
        try:
            await run_pipeline(db, document_id, test_suite_id)
        except Exception as e:
            logger.error(f"Background pipeline failed: {e}")
            # Ensure suite is marked as failed
            suite = await db.get(TestSuite, test_suite_id)
            if suite and suite.status == "generating":
                suite.status = "failed"
                suite.error_message = str(e)
                await db.commit()


@router.post(
    "/api/documents/{document_id}/generate",
    response_model=GenerationStartResponse,
)
async def start_generation(document_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger test suite generation for a document."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Check if already generating
    existing = await db.execute(
        select(TestSuite).where(
            TestSuite.document_id == document_id,
            TestSuite.status == "generating",
        )
    )
    if existing.scalars().first():
        raise HTTPException(409, "Generation already in progress for this document")

    # Determine version number
    max_version = await db.scalar(
        select(func.max(TestSuite.version)).where(TestSuite.document_id == document_id)
    )
    new_version = (max_version or 0) + 1

    # Create test suite record
    suite = TestSuite(
        document_id=document_id,
        version=new_version,
        status="generating",
    )
    db.add(suite)
    await db.flush()

    suite_id = suite.id

    # Commit so the background task can see the suite
    await db.commit()

    # Launch background task
    asyncio.create_task(_run_pipeline_background(document_id, suite_id))

    return GenerationStartResponse(
        test_suite_id=suite_id,
        status="generating",
        message="Generation started. Poll /generate/status for updates.",
    )


@router.get(
    "/api/documents/{document_id}/generate/status",
    response_model=GenerationStatusResponse,
)
async def get_generation_status(document_id: str, db: AsyncSession = Depends(get_db)):
    """Poll the latest generation status for a document."""
    stmt = (
        select(TestSuite)
        .where(TestSuite.document_id == document_id)
        .order_by(TestSuite.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    suite = result.scalars().first()

    if not suite:
        raise HTTPException(404, "No test suite found for this document")

    tc_count = await db.scalar(
        select(func.count(TestCase.id)).where(TestCase.test_suite_id == suite.id)
    ) or 0

    return GenerationStatusResponse(
        test_suite_id=suite.id,
        status=suite.status,
        coverage_score=suite.coverage_score,
        test_case_count=tc_count,
        error_message=suite.error_message,
    )


@router.get(
    "/api/documents/{document_id}/requirements",
    response_model=list[RequirementResponse],
)
async def get_requirements(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get extracted requirements for a document."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    stmt = (
        select(Requirement)
        .where(Requirement.document_id == document_id)
        .order_by(Requirement.order_index)
    )
    result = await db.execute(stmt)
    reqs = result.scalars().all()

    return [
        RequirementResponse(
            id=r.id,
            requirement_text=r.requirement_text,
            category=r.category,
            priority=r.priority,
            order_index=r.order_index,
        )
        for r in reqs
    ]
