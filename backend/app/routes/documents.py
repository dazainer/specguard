from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Project, Document, Requirement, TestSuite
from app.schemas.api import DocumentResponse, DocumentListResponse
from app.services.file_parser import parse_file, FileParseError

router = APIRouter(tags=["documents"])


@router.post(
    "/api/projects/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "File is empty")

    # Size limit: 5MB
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5MB)")

    # Parse file
    try:
        file_type, raw_text = parse_file(file.filename, content)
    except FileParseError as e:
        raise HTTPException(400, str(e))

    # Save to database
    doc = Document(
        project_id=project_id,
        filename=file.filename,
        file_type=file_type,
        raw_text=raw_text,
    )
    db.add(doc)
    await db.flush()

    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        filename=doc.filename,
        file_type=doc.file_type,
        raw_text=doc.raw_text,
        uploaded_at=doc.uploaded_at,
        requirement_count=0,
        test_suite_count=0,
    )


@router.get(
    "/api/projects/{project_id}/documents",
    response_model=list[DocumentListResponse],
)
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    stmt = (
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.uploaded_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()

    response = []
    for doc in docs:
        req_count = await db.scalar(
            select(func.count(Requirement.id)).where(Requirement.document_id == doc.id)
        ) or 0
        response.append(
            DocumentListResponse(
                id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                uploaded_at=doc.uploaded_at,
                requirement_count=req_count,
            )
        )
    return response


@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    req_count = await db.scalar(
        select(func.count(Requirement.id)).where(Requirement.document_id == document_id)
    ) or 0
    suite_count = await db.scalar(
        select(func.count(TestSuite.id)).where(TestSuite.document_id == document_id)
    ) or 0

    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        filename=doc.filename,
        file_type=doc.file_type,
        raw_text=doc.raw_text,
        uploaded_at=doc.uploaded_at,
        requirement_count=req_count,
        test_suite_count=suite_count,
    )


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    await db.delete(doc)
