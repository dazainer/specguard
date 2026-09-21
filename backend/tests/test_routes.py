from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models import models
from app.routes import generation
from app.services import pipeline
from app.services.ai_client import AIClientError
from tests.test_file_parser import make_pdf


async def test_health(client):
    assert (await client.get("/api/health")).json() == {"status": "ok", "service": "specguard"}


async def test_project_crud(client):
    response = await client.post("/api/projects", json={"name": "Example", "description": "A specification"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    assert (await client.get("/api/projects")).json()[0]["id"] == project_id
    detail = (await client.get(f"/api/projects/{project_id}")).json()
    assert detail["name"] == "Example" and detail["document_count"] == 0
    response = await client.put(f"/api/projects/{project_id}", json={"name": "Renamed"})
    assert response.status_code == 200 and response.json()["name"] == "Renamed"
    assert (await client.get(f"/api/projects/{project_id}")).json()["name"] == "Renamed"
    assert (await client.delete(f"/api/projects/{project_id}")).status_code == 204
    assert (await client.get(f"/api/projects/{project_id}")).status_code == 404


@pytest.mark.parametrize("name", ["", "x" * 256])
async def test_invalid_project(client, name):
    assert (await client.post("/api/projects", json={"name": name})).status_code == 422
    assert (await client.get("/api/projects")).json() == []


@pytest.mark.parametrize("extension", ["txt", "md", "pdf"])
async def test_document_upload_read_delete(client, extension):
    project = (await client.post("/api/projects", json={"name": "Upload"})).json()
    text = "Users can log in using their email and password."
    content = make_pdf(text) if extension == "pdf" else text.encode()
    response = await client.post(f"/api/projects/{project['id']}/documents", files={"file": (f"spec.{extension}", content)})
    assert response.status_code == 201
    document = response.json()
    assert document["raw_text"] == text and document["file_type"] == extension
    assert (await client.get(f"/api/documents/{document['id']}")).json()["raw_text"] == text
    assert len((await client.get(f"/api/projects/{project['id']}/documents")).json()) == 1
    assert (await client.get(f"/api/projects/{project['id']}")).json()["document_count"] == 1
    assert (await client.delete(f"/api/documents/{document['id']}")).status_code == 204
    assert (await client.get(f"/api/documents/{document['id']}")).status_code == 404


@pytest.mark.parametrize("filename, content", [
    ("empty.txt", b""), ("short.md", b"short"), ("bad.exe", b"x" * 30),
    ("bad.pdf", b"not a PDF"), ("large.txt", b"x" * (5 * 1024 * 1024 + 1)),
])
async def test_invalid_upload_does_not_persist(client, seeded, filename, content):
    response = await client.post(f"/api/projects/{seeded[0]}/documents", files={"file": (filename, content)})
    assert response.status_code == 400
    assert len((await client.get(f"/api/projects/{seeded[0]}/documents")).json()) == 1


@pytest.mark.parametrize("path", [
    "/api/projects/missing", "/api/projects/missing/stats", "/api/projects/missing/documents",
    "/api/documents/missing", "/api/documents/missing/requirements",
    "/api/documents/missing/test-suites", "/api/documents/missing/generate/status",
    "/api/test-suites/missing", "/api/test-suites/missing/test-cases", "/api/test-suites/missing/export",
])
async def test_missing_resources(client, path):
    assert (await client.get(path)).status_code == 404


@pytest.fixture
async def completed(db, seeded, fake_ai, extraction, generated):
    fake_ai(extraction, generated, generated)
    await pipeline.run_pipeline(db, seeded[1], seeded[2])
    return seeded


async def test_suite_review_filters_and_exports(client, completed):
    project_id, document_id, suite_id = completed
    suites = (await client.get(f"/api/documents/{document_id}/test-suites")).json()
    assert suites[0]["test_case_count"] == 2 and suites[0]["status"] == "completed"
    suite = (await client.get(f"/api/test-suites/{suite_id}")).json()
    assert suite["metadata_"]["total_requirements"] == 2
    assert len((await client.get(f"/api/documents/{document_id}/requirements")).json()) == 2
    cases_url = f"/api/test-suites/{suite_id}/test-cases"
    cases = (await client.get(cases_url)).json()
    case_id = cases[0]["id"]
    for status in ["approved", "rejected"]:
        response = await client.patch(f"/api/test-cases/{case_id}", json={"status": status})
        assert response.json()["status"] == status
        assert len((await client.get(cases_url, params={"status": status})).json()) == 1
    response = await client.patch(f"/api/test-cases/{case_id}", json={"title": "Edited test title"})
    assert response.json()["status"] == "edited"
    assert (await client.get(cases_url, params={"test_type": "negative"})).json() == []
    assert len((await client.get(cases_url, params={"priority": "high"})).json()) == 2
    assert (await client.get(cases_url, params={"test_type": "invalid"})).status_code == 422
    stats = (await client.get(f"/api/projects/{project_id}/stats")).json()
    assert stats["total_test_cases"] == 2 and stats["status_breakdown"]["edited"] == 1
    response = await client.get(f"/api/test-suites/{suite_id}/export?format=json")
    assert response.headers["content-type"] == "application/json"
    assert "test-suite-v1.json" in response.headers["content-disposition"]
    export = response.json()
    assert len(export["test_cases"]) == 2
    assert all(case["requirement"] for case in export["test_cases"])
    assert any(case["title"] == "Edited test title" for case in export["test_cases"])
    response = await client.get(f"/api/test-suites/{suite_id}/export?format=md")
    assert "test-suite-v1.md" in response.headers["content-disposition"]
    assert "# Test Suite v1" in response.text and "Edited test title" in response.text
    assert "1. Enter valid credentials" in response.text
    assert (await client.get(f"/api/test-suites/{suite_id}/export?format=csv")).status_code == 422


async def test_zero_score_is_not_missing(client, db, completed):
    suite = await db.get(models.TestSuite, completed[2])
    suite.coverage_score = 0.0
    await db.commit()
    assert (await client.get(f"/api/projects/{completed[0]}/stats")).json()["avg_coverage_score"] == 0.0
    response = await client.get(f"/api/test-suites/{completed[2]}/export?format=md")
    assert "**Coverage Score:** 0.0" in response.text


@pytest.mark.parametrize("resource", ["projects", "documents"])
async def test_delete_cascades(client, db, completed, resource):
    resource_id = completed[0] if resource == "projects" else completed[1]
    assert (await client.delete(f"/api/{resource}/{resource_id}")).status_code == 204
    for model in [models.Document, models.Requirement, models.TestSuite, models.TestCase]:
        assert await db.scalar(select(func.count(model.id))) == 0


@pytest.fixture
def queued_tasks(monkeypatch, session_factory):
    queued = []
    monkeypatch.setattr(generation, "asyncio", SimpleNamespace(create_task=queued.append))
    monkeypatch.setattr(generation, "async_session", session_factory)
    try:
        yield queued
    finally:
        for coroutine in queued:
            coroutine.close()


@pytest.mark.parametrize("fails", [False, True])
async def test_background_generation_status(client, db, seeded, queued_tasks, fake_ai, extraction, generated, fails):
    # Remove the seed suite, so the API creates and commits the first generation itself.
    await db.delete(await db.get(models.TestSuite, seeded[2]))
    await db.commit()
    if fails:
        fake_ai(AIClientError("fake extraction failed"))
    else:
        fake_ai(extraction, generated, generated)
    url = f"/api/documents/{seeded[1]}/generate"
    response = await client.post(url)
    assert response.status_code == 200
    assert response.json()["status"] == "generating"
    assert (await client.get(url + "/status")).json()["status"] == "generating"
    assert (await client.post(url)).status_code == 409
    assert len(queued_tasks) == 1
    await queued_tasks.pop(0)
    status = (await client.get(url + "/status")).json()
    assert status["status"] == ("failed" if fails else "completed")
    assert status["test_case_count"] == (0 if fails else 2)
    assert bool(status["error_message"]) == fails
    # A terminal suite permits another generation and increments the version.
    assert (await client.post(url)).status_code == 200
    suites = (await client.get(f"/api/documents/{seeded[1]}/test-suites")).json()
    assert [suite["version"] for suite in suites] == [2, 1]


async def test_generate_missing_document(client, queued_tasks):
    assert (await client.post("/api/documents/missing/generate")).status_code == 404
    assert queued_tasks == []
