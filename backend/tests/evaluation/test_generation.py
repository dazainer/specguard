import json

import pytest

from app.evaluation.generation import generate
from app.evaluation.providers import Completion, ProviderFailure


class SequenceProvider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete(self, system, user, config):
        self.calls.append((system, user, config))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return Completion(response, input_tokens=10, output_tokens=20)


async def no_sleep(_):
    pass


@pytest.mark.parametrize('bad', ['', '{', '{"files":[]}', json.dumps({'files':[{'path':'../escape.py','content':'pass'}]}),
    json.dumps({'files':[{'path':'.specguard/generated_tests/test_bad.py','content':'def invalid('}]}),
    ProviderFailure('provider_connection', True)])
async def test_retry_invalid_and_transient_outputs(bad, manifest, subject, tmp_path):
    configured = manifest.model_copy(update={'generation': manifest.generation.model_copy(update={'prompt_version':'contract-v1'})})
    provider = SequenceProvider([bad, (subject / 'generation-fixture.json').read_text()])
    artifacts, metrics = await generate(provider, configured, {'specification':'public'}, tmp_path, sleep=no_sleep)
    assert artifacts and metrics.successful and metrics.attempts == 2
    assert len(provider.calls) == 2
    attempts = json.loads((tmp_path / 'attempts.json').read_text())
    assert attempts[-1]['status'] == 'valid'
    assert 'public' not in (tmp_path / 'attempts.json').read_text()
    assert (tmp_path / 'prompt.json').is_file()


@pytest.mark.parametrize('error', [ProviderFailure('provider_http_401',False), RuntimeError('secret-provider-body')])
async def test_terminal_errors_do_not_retry_or_leak(error, manifest, tmp_path):
    configured = manifest.model_copy(update={'generation':manifest.generation.model_copy(update={'prompt_version':'contract-v1'})})
    provider = SequenceProvider([error])
    artifacts, metrics = await generate(provider, configured, {}, tmp_path, sleep=no_sleep)
    assert artifacts is None and not metrics.successful and metrics.attempts == 1
    assert 'secret-provider-body' not in (tmp_path/'attempts.json').read_text()


async def test_retry_budget_and_sanitized_feedback(manifest, tmp_path):
    configured = manifest.model_copy(update={'generation':manifest.generation.model_copy(update={'prompt_version':'boundary-v1'})})
    provider = SequenceProvider(['secret-invalid-response'] * 3)
    artifacts, metrics = await generate(provider, configured, {}, tmp_path, sleep=no_sleep)
    assert artifacts is None and metrics.attempts == 3
    assert metrics.input_tokens == 30 and metrics.output_tokens == 60
    assert all('secret-invalid-response' not in call[1] for call in provider.calls)


async def test_openai_adapter_uses_manifest_config_without_live_calls(monkeypatch, manifest):
    from types import SimpleNamespace
    from app.evaluation import providers
    calls = []
    async def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))],
            usage=SimpleNamespace(prompt_tokens=12,completion_tokens=7),model='resolved-model',system_fingerprint='test-fingerprint')
    fake = SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(providers, 'AIClient', lambda:fake)
    response = await providers.OpenAIProvider().complete('system','user',manifest.generation)
    assert response.input_tokens == 12 and response.output_tokens == 7
    assert calls[0]['model'] == manifest.generation.model
    assert calls[0]['timeout'] == 60 and calls[0]['max_tokens'] == 4096
