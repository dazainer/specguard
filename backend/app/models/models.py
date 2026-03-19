import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="project", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Document
# ──────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    raw_text: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="documents")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    test_suites: Mapped[list["TestSuite"]] = relationship(back_populates="document", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Requirement (extracted by AI)
# ──────────────────────────────────────────────
class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50))
    priority: Mapped[str] = mapped_column(String(20))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped["Document"] = relationship(back_populates="requirements")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="requirement")


# ──────────────────────────────────────────────
# Test Suite (one generation run = one suite)
# ──────────────────────────────────────────────
class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="generating")  # generating | completed | failed
    coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="test_suites")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="test_suite", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Test Case
# ──────────────────────────────────────────────
class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    test_suite_id: Mapped[str] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"))
    requirement_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    test_type: Mapped[str] = mapped_column(String(50))  # functional | edge_case | negative
    preconditions: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    expected_result: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="generated")  # generated | approved | rejected | edited
    tags: Mapped[list] = mapped_column(JSON, default=list)

    test_suite: Mapped["TestSuite"] = relationship(back_populates="test_cases")
    requirement: Mapped["Requirement | None"] = relationship(back_populates="test_cases")
