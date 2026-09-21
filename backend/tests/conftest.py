"""Deterministic tests: temporary databases, fake AI, and no outbound sockets."""

import os
import socket
from collections import deque

# Set these before importing application modules; never use the developer's .env/database.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app import main
from app.models import models
from app.services import pipeline


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Automated tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory, monkeypatch):
    async def override_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def initialized_test_db():
        pass  # session_factory already initialized this test's temporary database.

    monkeypatch.setattr(main, "init_db", initialized_test_db)
    main.app.dependency_overrides[get_db] = override_db
    try:
        async with main.app.router.lifespan_context(main.app):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as http:
                yield http
    finally:
        main.app.dependency_overrides.clear()


@pytest.fixture
async def seeded(db):
    project = models.Project(name="Authentication", description="Test project")
    db.add(project)
    await db.flush()
    document = models.Document(
        project_id=project.id, filename="spec.md", file_type="md",
        raw_text="Users can log in and reset their passwords.",
    )
    db.add(document)
    await db.flush()
    suite = models.TestSuite(document_id=document.id, status="generating", version=1)
    db.add(suite)
    await db.commit()
    return project.id, document.id, suite.id


@pytest.fixture
def extraction():
    return {"requirements": [
        {"requirement_text": "Users can log in with valid credentials", "category": "functional", "priority": "high"},
        {"requirement_text": "Users can reset a forgotten password", "category": "security", "priority": "medium"},
    ]}


@pytest.fixture
def generated():
    return {"test_cases": [{
        "title": "Verify successful user login",
        "description": "A registered user can log in successfully",
        "test_type": "functional", "preconditions": "Registered account",
        "steps": ["Enter valid credentials", "Submit the login form"],
        "expected_result": "The user's dashboard is displayed",
        "priority": "high", "tags": ["auth"],
    }]}


@pytest.fixture
def fake_ai(monkeypatch):
    def install(*outcomes):
        class FakeAI:
            model = "deterministic-fake"

            def __init__(self):
                self.outcomes = deque(outcomes)
                self.calls = []

            async def generate_structured(self, **kwargs):
                self.calls.append(kwargs)
                outcome = self.outcomes.popleft()
                if isinstance(outcome, Exception):
                    raise outcome
                return kwargs["output_schema"].model_validate(outcome)

        fake = FakeAI()
        monkeypatch.setattr(pipeline, "AIClient", lambda: fake)
        return fake

    return install
