"""Handwritten native suite. Never included in model context."""

import pytest

from src.reservations import cancellation_refund, quote


@pytest.mark.parametrize("nights, rate, guests, member, expected", [
    (1, 10000, 1, False, 10000),
    (1, 10000, 2, False, 10000),
    (1, 10000, 3, False, 12000),
    (6, 10000, 2, False, 60000),
    (7, 10000, 2, False, 63000),
    (7, 10000, 3, True, 71820),
    (1, 101, 1, True, 95),
    (30, 0, 6, False, 216000),
])
def test_quote(nights, rate, guests, member, expected):
    assert quote(nights, rate, guests, member) == expected


@pytest.mark.parametrize("kwargs", [
    {"nights": 0}, {"nights": 31}, {"nightly_rate_cents": -1},
    {"nightly_rate_cents": 100001}, {"guests": 0}, {"guests": 7},
])
def test_quote_invalid_range(kwargs):
    values = {"nights": 1, "nightly_rate_cents": 10000, **kwargs}
    with pytest.raises(ValueError):
        quote(**values)


@pytest.mark.parametrize("kwargs", [
    {"nights": True}, {"nightly_rate_cents": 10.0}, {"guests": "2"}, {"member": 1},
])
def test_quote_invalid_type(kwargs):
    values = {"nights": 1, "nightly_rate_cents": 10000, **kwargs}
    with pytest.raises(TypeError):
        quote(**values)


@pytest.mark.parametrize("days, expected", [(0, 0), (1, 0), (2, 50), (6, 50), (7, 101), (365, 101)])
def test_refund_boundaries(days, expected):
    assert cancellation_refund(101, days) == expected


@pytest.mark.parametrize("total, days, error", [
    (-1, 7, ValueError), (10000001, 7, ValueError), (100, -1, ValueError),
    (100, 366, ValueError), (True, 7, TypeError), (100, 1.5, TypeError),
])
def test_invalid_refund(total, days, error):
    with pytest.raises(error):
        cancellation_refund(total, days)
