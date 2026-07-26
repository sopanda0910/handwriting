"""Gemini spend metering and the daily budget cap.

Every Gemini call is metered from the API's own usage_metadata token counts
and priced at the configured per-million rates. The ledger persists per-day
in the storage directory; once today's estimated spend reaches the budget,
further calls raise BudgetExceededError instead of billing.

This is an application-level guard: it caps what THIS app spends. Set a
Google Cloud budget alert on the project as the authoritative backstop.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from ..config import settings


class BudgetExceededError(RuntimeError):
    pass


_lock = threading.Lock()


def _ledger_path() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "gemini_usage.json"


def _load() -> dict:
    path = _ledger_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _today() -> str:
    return date.today().isoformat()


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.gemini_price_input_per_m
        + output_tokens * settings.gemini_price_output_per_m
    ) / 1_000_000


def today_usage() -> dict:
    data = _load().get(_today(), {})
    return {
        "date": _today(),
        "calls": data.get("calls", 0),
        "input_tokens": data.get("input_tokens", 0),
        "output_tokens": data.get("output_tokens", 0),
        "cost_usd": round(data.get("cost_usd", 0.0), 4),
        "budget_usd": settings.gemini_daily_budget_usd,
    }


def check_budget() -> None:
    """Raise if today's estimated spend has reached the daily budget."""
    usage = today_usage()
    if usage["cost_usd"] >= settings.gemini_daily_budget_usd:
        raise BudgetExceededError(
            f"Gemini daily budget reached: ${usage['cost_usd']:.2f} of "
            f"${settings.gemini_daily_budget_usd:.2f} spent today "
            f"({usage['calls']} calls). Raise HWP_GEMINI_DAILY_BUDGET_USD or "
            "wait until tomorrow."
        )


def record_usage(usage_metadata) -> float:
    """Record one call's token usage; returns its estimated cost in USD."""
    input_tokens = int(getattr(usage_metadata, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage_metadata, "candidates_token_count", 0) or 0)
    output_tokens += int(getattr(usage_metadata, "thoughts_token_count", 0) or 0)
    cost = estimate_cost(input_tokens, output_tokens)

    with _lock:
        data = _load()
        day = data.setdefault(_today(), {
            "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        })
        day["calls"] += 1
        day["input_tokens"] += input_tokens
        day["output_tokens"] += output_tokens
        day["cost_usd"] += cost
        _ledger_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return cost
