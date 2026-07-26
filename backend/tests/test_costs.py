"""Gemini spend metering and the daily budget cap."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hwportfolio.transcribe import costs


@pytest.fixture(autouse=True)
def clean_ledger():
    path = costs._ledger_path()
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


def usage_meta(prompt=1000, candidates=200, thoughts=300):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
    )


def test_cost_estimate_uses_configured_prices():
    # 1M input at $1.50 + 1M output at $7.50
    assert costs.estimate_cost(1_000_000, 1_000_000) == pytest.approx(9.0)


def test_thinking_tokens_bill_as_output():
    cost_with = costs.record_usage(usage_meta(thoughts=1000))
    assert cost_with == pytest.approx(costs.estimate_cost(1000, 1200))


def test_ledger_accumulates_across_calls():
    costs.record_usage(usage_meta())
    costs.record_usage(usage_meta())
    usage = costs.today_usage()
    assert usage["calls"] == 2
    assert usage["input_tokens"] == 2000
    assert usage["output_tokens"] == 1000
    assert usage["cost_usd"] > 0


def test_budget_cap_blocks_when_reached(monkeypatch):
    costs.check_budget()  # fresh day passes
    monkeypatch.setattr(costs.settings, "gemini_daily_budget_usd", 0.001)
    # One large call takes us past the tiny budget...
    costs.record_usage(usage_meta(prompt=500_000, candidates=100_000, thoughts=0))
    with pytest.raises(costs.BudgetExceededError) as excinfo:
        costs.check_budget()
    assert "daily budget" in str(excinfo.value).lower()
