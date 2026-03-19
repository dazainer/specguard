import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Document, TestSuite, TestCase, Requirement
from app.schemas.api import (
    TestSuiteResponse,
    TestSuiteListResponse,
    TestCaseResponse,
    TestCaseUpdate,
)

router = APIRouter(tags=["test-suites"])


# ──────────────────────────────────────────────
# Test Suites
# ──────────────────────────────────────────────
@router.get(
    "/api/documents/{document_id}/test-suites",
    response_model=list[TestSuiteListResponse],
)
async def list_test_suites(document_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    stmt = (
        select(TestSuite)
        .where(TestSuite.document_id == document_id)
        .order_by(TestSuite.version.desc())
    )
    result = await db.execute(stmt)
    suites = result.scalars().all()

    response = []
    for s in suites:
        tc_count = await db.scalar(
            select(func.count(TestCase.id)).where(TestCase.test_suite_id == s.id)
        ) or 0
        response.append(
            TestSuiteListResponse(
                id=s.id,
                version=s.version,
                status=s.status,
                coverage_score=s.coverage_score,
                created_at=s.created_at,
                test_case_count=tc_count,
            )
        )
    return response


@router.get("/api/test-suites/{suite_id}", response_model=TestSuiteResponse)
async def get_test_suite(suite_id: str, db: AsyncSession = Depends(get_db)):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(404, "Test suite not found")
    return suite


# ──────────────────────────────────────────────
# Test Cases
# ──────────────────────────────────────────────
@router.get(
    "/api/test-suites/{suite_id}/test-cases",
    response_model=list[TestCaseResponse],
)
async def list_test_cases(
    suite_id: str,
    test_type: str | None = Query(None, pattern="^(functional|edge_case|negative)$"),
    status: str | None = Query(None, pattern="^(generated|approved|rejected|edited)$"),
    priority: str | None = Query(None, pattern="^(critical|high|medium|low)$"),
    db: AsyncSession = Depends(get_db),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(404, "Test suite not found")

    stmt = select(TestCase).where(TestCase.test_suite_id == suite_id)

    if test_type:
        stmt = stmt.where(TestCase.test_type == test_type)
    if status:
        stmt = stmt.where(TestCase.status == status)
    if priority:
        stmt = stmt.where(TestCase.priority == priority)

    stmt = stmt.order_by(TestCase.requirement_id, TestCase.test_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/api/test-cases/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    test_case_id: str,
    data: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    tc = await db.get(TestCase, test_case_id)
    if not tc:
        raise HTTPException(404, "Test case not found")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(tc, field, value)

    # If content was edited, mark status as edited
    content_fields = {"title", "description", "steps", "expected_result"}
    if content_fields & update_fields.keys():
        tc.status = "edited"

    await db.flush()
    return tc


# ──────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────
@router.get("/api/test-suites/{suite_id}/export")
async def export_test_suite(
    suite_id: str,
    format: str = Query("json", pattern="^(json|md)$"),
    db: AsyncSession = Depends(get_db),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(404, "Test suite not found")

    # Load test cases
    stmt = select(TestCase).where(TestCase.test_suite_id == suite_id)
    result = await db.execute(stmt)
    test_cases = result.scalars().all()

    # Load requirements for context
    doc = await db.get(Document, suite.document_id)
    req_stmt = select(Requirement).where(Requirement.document_id == suite.document_id)
    req_result = await db.execute(req_stmt)
    requirements = {r.id: r for r in req_result.scalars().all()}

    if format == "json":
        export_data = {
            "test_suite_id": suite.id,
            "document": doc.filename if doc else "Unknown",
            "version": suite.version,
            "coverage_score": suite.coverage_score,
            "score_breakdown": suite.score_breakdown,
            "test_cases": [
                {
                    "title": tc.title,
                    "description": tc.description,
                    "test_type": tc.test_type,
                    "requirement": requirements[tc.requirement_id].requirement_text
                    if tc.requirement_id and tc.requirement_id in requirements
                    else None,
                    "preconditions": tc.preconditions,
                    "steps": tc.steps,
                    "expected_result": tc.expected_result,
                    "priority": tc.priority,
                    "status": tc.status,
                    "tags": tc.tags,
                }
                for tc in test_cases
            ],
        }
        return Response(
            content=json.dumps(export_data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="test-suite-v{suite.version}.json"'},
        )

    else:  # markdown
        lines = [
            f"# Test Suite v{suite.version}",
            f"**Document:** {doc.filename if doc else 'Unknown'}",
            f"**Coverage Score:** {suite.coverage_score or 'N/A'}",
            "",
        ]
        for i, tc in enumerate(test_cases, 1):
            req_text = (
                requirements[tc.requirement_id].requirement_text
                if tc.requirement_id and tc.requirement_id in requirements
                else "N/A"
            )
            lines.append(f"## TC-{i:03d}: {tc.title}")
            lines.append(f"- **Type:** {tc.test_type}")
            lines.append(f"- **Priority:** {tc.priority}")
            lines.append(f"- **Requirement:** {req_text}")
            lines.append(f"- **Preconditions:** {tc.preconditions}")
            lines.append(f"- **Steps:**")
            for j, step in enumerate(tc.steps, 1):
                lines.append(f"  {j}. {step}")
            lines.append(f"- **Expected Result:** {tc.expected_result}")
            lines.append(f"- **Tags:** {', '.join(tc.tags) if tc.tags else 'None'}")
            lines.append("")

        return Response(
            content="\n".join(lines),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="test-suite-v{suite.version}.md"'},
        )
