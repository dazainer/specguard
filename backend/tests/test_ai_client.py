import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from app.schemas.ai_output import RequirementExtractionResult
from app.services import ai_client


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setattr(ai_client, "_stats", dict(total_calls=0, first_pass=0, retries=0, failures=0))

    def factory(*outcomes):
        responses = [
            item if isinstance(item, Exception) else SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=item))]
            ) for item in outcomes
        ]
        create = AsyncMock(side_effect=responses)

        def fake_openai(**kwargs):
            assert kwargs["max_retries"] == 0  # One retry budget, no hidden SDK retries.
            return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        monkeypatch.setattr(ai_client, "AsyncOpenAI", fake_openai)
        client = ai_client.AIClient()
        client.max_retries = 2
        return client, create

    return factory


async def generate(client):
    return await client.generate_structured("system", "specification", RequirementExtractionResult)


async def test_first_pass(make_client, extraction):
    client, create = make_client(json.dumps(extraction))
    assert len((await generate(client)).requirements) == 2
    assert create.await_count == 1
    assert ai_client.get_validation_stats()["first_pass_rate"] == 1


@pytest.mark.parametrize("bad", ['{"requirements": []}', "not JSON", "", None, "   "])
async def test_invalid_output_retries_with_feedback(make_client, extraction, bad):
    client, create = make_client(bad, json.dumps(extraction))
    assert len((await generate(client)).requirements) == 2
    assert create.await_count == 2
    assert "validation errors" in create.call_args.kwargs["messages"][1]["content"]
    stats = ai_client.get_validation_stats()
    assert stats["retries"] == 1 and stats["failures"] == 0


@pytest.mark.parametrize("bad", ['{"requirements": []}', "{", "", None])
async def test_invalid_output_exhausts_budget(make_client, bad):
    client, create = make_client(bad, bad, bad)
    with pytest.raises(ai_client.AIClientError, match="after 3 attempts"):
        await generate(client)
    assert create.await_count == 3
    assert ai_client.get_validation_stats()["failure_rate"] == 1


@pytest.mark.parametrize("status, calls", [(408, 2), (409, 2), (429, 2), (500, 2), (503, 2), (400, 1), (401, 1)])
async def test_provider_retry_policy(make_client, extraction, status, calls):
    response = httpx.Response(status, request=httpx.Request("POST", "https://test.invalid"))
    error = APIStatusError("sensitive provider payload", response=response, body=None)
    client, create = make_client(error, json.dumps(extraction))
    if calls == 2:
        await generate(client)
    else:
        with pytest.raises(ai_client.AIClientError, match=f"HTTP {status}") as caught:
            await generate(client)
        assert "sensitive" not in str(caught.value)
    assert create.await_count == calls


async def test_connection_retry(make_client, extraction):
    error = APIConnectionError(request=httpx.Request("POST", "https://test.invalid"))
    client, create = make_client(error, json.dumps(extraction))
    await generate(client)
    assert create.await_count == 2


async def test_zero_retry_budget(make_client):
    client, create = make_client("")
    client.max_retries = 0
    with pytest.raises(ai_client.AIClientError, match="after 1 attempts"):
        await generate(client)
    assert create.await_count == 1
