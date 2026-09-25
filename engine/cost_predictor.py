#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Session cost predictor — estimate token spend before committing to a task.

Pure function: reads sessions.json history, returns estimated cost and
budget recommendation. No side effects.
"""
import json
from pathlib import Path
from typing import Optional

from registry import ProjectContext
from models import DEFAULT_DAILY_LIMIT_USD

# Default estimate when no history exists (conservative mid-range)
_DEFAULT_COST_USD = 0.35
_HISTORY_WINDOW = 10  # only use last N matching sessions


def predict_session_cost(ctx: ProjectContext, session_type: str,
                         daily_limit: Optional[float] = None,
                         spent_today: Optional[float] = None) -> dict:
    """Predict cost of next session based on historical averages.

    Returns dict with:
        estimated_cost: float (USD)
        confidence: "low" | "medium" | "high"
        recommend: "proceed" | "skip"
        reason: str
    """
    # Load session history
    sessions = _load_sessions(ctx.sessions_file)

    # Filter to matching session type, take last N
    matching = [s for s in sessions if s.get("type") == session_type and s.get("cost_usd")]
    recent = matching[-_HISTORY_WINDOW:]

    # Compute estimate
    if not recent:
        estimated = _DEFAULT_COST_USD
        confidence = "low"
    else:
        costs = [s["cost_usd"] for s in recent]
        estimated = round(sum(costs) / len(costs), 4)
        confidence = "high" if len(recent) >= 5 else "medium"

    # Budget check
    limit = daily_limit or ctx.config.get("daily_limit_usd", DEFAULT_DAILY_LIMIT_USD)
    today_spent = spent_today if spent_today is not None else _get_today_spend(ctx)
    remaining = limit - today_spent

    if estimated > remaining:
        recommend = "skip"
        reason = f"Predicted ${estimated:.2f} exceeds remaining budget ${remaining:.2f}"
    else:
        recommend = "proceed"
        reason = f"Predicted ${estimated:.2f} fits in remaining ${remaining:.2f}"

    return {
        "estimated_cost": estimated,
        "confidence": confidence,
        "recommend": recommend,
        "reason": reason,
        "history_count": len(recent),
    }


def _load_sessions(sessions_file: Path) -> list:
    """Load sessions.json, return empty list on any error."""
    if not sessions_file.exists():
        return []
    try:
        data = json.loads(sessions_file.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_today_spend(ctx: ProjectContext) -> float:
    """Read today's spend from daily_budget.json."""
    from datetime import date
    if not ctx.budget_file.exists():
        return 0.0
    try:
        data = json.loads(ctx.budget_file.read_text(encoding="utf-8"))
        return data.get(str(date.today()), 0.0)
    except Exception:
        return 0.0
