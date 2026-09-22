import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.evaluation.budget import MODEL, RESERVATION, SpendBudget
from app.evaluation.providers import ProviderFailure, OpenAIProvider


def test_budget_persists_and_rejects_excess_or_different_model(tmp_path):
    path = tmp_path/'budget.json'
    SpendBudget(path, RESERVATION).reserve(MODEL)
    with pytest.raises(ProviderFailure, match='budget_exhausted'):
        SpendBudget(path, RESERVATION).reserve(MODEL)
    with pytest.raises(ValueError): SpendBudget(path, RESERVATION).reserve('another-model')
    with pytest.raises(ValueError): SpendBudget(path, '2').reserve(MODEL)
    assert json.loads(path.read_text())['attempts'] == 1


def test_concurrent_reservations_do_not_overspend(tmp_path):
    budget = SpendBudget(tmp_path/'budget.json', RESERVATION * 2)
    def attempt(_):
        try:
            budget.reserve(MODEL)
            return True
        except ProviderFailure:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(8))) == 2


@pytest.mark.parametrize('limit', ['0','-1','NaN','Infinity','6','abc'])
def test_invalid_ceiling_rejected(tmp_path, limit):
    with pytest.raises(ValueError): SpendBudget(tmp_path/'budget.json', limit)


async def test_provider_reserves_before_http_and_keeps_failed_charge(tmp_path, monkeypatch, manifest):
    from app.evaluation import providers
    calls = []
    async def create(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('transport interrupted')
    fake = SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(providers, 'AIClient', lambda: fake)
    path = tmp_path/'budget.json'
    provider = OpenAIProvider(SpendBudget(path, RESERVATION))
    config = manifest.generation.model_copy(update={'model':MODEL})
    with pytest.raises(RuntimeError): await provider.complete('system','user',config)
    with pytest.raises(ProviderFailure): await provider.complete('system','user',config)
    assert len(calls) == 1
    assert Decimal(json.loads(path.read_text())['reserved_usd']) == RESERVATION


def test_usage_cost_is_conservative_uncached_estimate():
    assert OpenAIProvider.cost(SimpleNamespace(prompt_tokens=1000, completion_tokens=1000)) == .00075
    assert OpenAIProvider.cost(None) is None
