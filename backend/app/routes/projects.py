from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Project, Document, TestCase, Requirement, TestSuite
from app.schemas.api import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectStatsResponse,
    TestSuiteListResponse,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.flush()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        document_count=0,
        total_test_cases=0,
    )


@router.get("", response_model=list[ProjectListResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = select(Project).order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    projects = result.scalars().all()

    response = []
    for p in projects:
        doc_count = await db.scalar(
            select(func.count(Document.id)).where(Document.project_id == p.id)
        )
        response.append(
            ProjectListResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                document_count=doc_count or 0,
            )
        )
    return response


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    doc_count = await db.scalar(
        select(func.count(Document.id)).where(Document.project_id == project_id)
    )
    tc_count = await db.scalar(
        select(func.count(TestCase.id))
        .join(TestSuite)
        .join(Document)
        .where(Document.project_id == project_id)
    )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        document_count=doc_count or 0,
        total_test_cases=tc_count or 0,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description

    await db.flush()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)


@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def get_project_stats(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    total_docs = await db.scalar(
        select(func.count(Document.id)).where(Document.project_id == project_id)
    ) or 0

    total_reqs = await db.scalar(
        select(func.count(Requirement.id))
        .join(Document)
        .where(Document.project_id == project_id)
    ) or 0

    total_suites = await db.scalar(
        select(func.count(TestSuite.id))
        .join(Document)
        .where(Document.project_id == project_id)
    ) or 0

    # Test cases with breakdowns
    tc_stmt = (
        select(TestCase)
        .join(TestSuite)
        .join(Document)
        .where(Document.project_id == project_id)
    )
    tc_result = await db.execute(tc_stmt)
    all_tcs = tc_result.scalars().all()

    type_breakdown: dict[str, int] = {}
    status_breakdown: dict[str, int] = {}
    for tc in all_tcs:
        type_breakdown[tc.test_type] = type_breakdown.get(tc.test_type, 0) + 1
        status_breakdown[tc.status] = status_breakdown.get(tc.status, 0) + 1

    # Avg coverage score
    avg_score = await db.scalar(
        select(func.avg(TestSuite.coverage_score))
        .join(Document)
        .where(Document.project_id == project_id, TestSuite.status == "completed")
    )

    # Recent generations
    recent_stmt = (
        select(TestSuite)
        .join(Document)
        .where(Document.project_id == project_id)
        .order_by(TestSuite.created_at.desc())
        .limit(5)
    )
    recent_result = await db.execute(recent_stmt)
    recent_suites = recent_result.scalars().all()

    recent_list = []
    for s in recent_suites:
        tc_count = await db.scalar(
            select(func.count(TestCase.id)).where(TestCase.test_suite_id == s.id)
        ) or 0
        recent_list.append(
            TestSuiteListResponse(
                id=s.id,
                version=s.version,
                status=s.status,
                coverage_score=s.coverage_score,
                created_at=s.created_at,
                test_case_count=tc_count,
            )
        )

    return ProjectStatsResponse(
        project_id=project.id,
        project_name=project.name,
        total_documents=total_docs,
        total_requirements=total_reqs,
        total_test_suites=total_suites,
        total_test_cases=len(all_tcs),
        avg_coverage_score=round(avg_score, 3) if avg_score else None,
        test_type_breakdown=type_breakdown,
        status_breakdown=status_breakdown,
        recent_generations=recent_list,
    )
