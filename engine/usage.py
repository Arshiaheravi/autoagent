#!/usr/bin/env python3
"""Usage tracking — per-project token consumption metering.

Tracks input/output tokens, cache usage, cost estimates, and session
counts per project per day. Designed for Max plan users who need
visibility into which projects are consuming their usage cap.

Storage: ~/.autoagent/projects/<name>/usage.json
Format: {
    "2026-04-06": {
        "sessions": 3,
        "input_tokens": 45000,
        "output_tokens": 12000,
        "cache_read_tokens": 90000,
        "cache_creation_tokens": 15000,
        "total_tokens": 162000,
        "cost_usd": 0.45,
        "duration_ms": 180000
    }
}
"""
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _usage_file(ctx) -> Path:
    """Return the usage.json path for a project."""
    return ctx.project_home / "usage.json"


def _load_usage(ctx) -> dict:
    """Load usage data from disk. Returns empty dict if missing."""
    uf = _usage_file(ctx)
    if not uf.exists():
        return {}
    try:
        return json.loads(uf.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_usage(ctx, data: dict):
    """Write usage data to disk."""
    uf = _usage_file(ctx)
    uf.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_session_usage(ctx, result_event: dict):
    """Extract token usage from a Claude CLI result event and record it.

    Called from run.py after each session completes.

    Args:
        ctx: ProjectContext
        result_event: The parsed JSON 'result' event from Claude CLI stream.
    """
    usage = result_event.get("usage", {})
    model_usage = result_event.get("modelUsage", {})

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    cost_usd = result_event.get("total_cost_usd", 0.0)
    duration_ms = result_event.get("duration_ms", 0)

    # Sum across all models if modelUsage is present
    if model_usage:
        input_tokens = sum(
            m.get("inputTokens", 0) for m in model_usage.values()
        )
        output_tokens = sum(
            m.get("outputTokens", 0) for m in model_usage.values()
        )
        cache_read = sum(
            m.get("cacheReadInputTokens", 0) for m in model_usage.values()
        )
        cache_creation = sum(
            m.get("cacheCreationInputTokens", 0) for m in model_usage.values()
        )
        cost_usd = sum(
            m.get("costUSD", 0.0) for m in model_usage.values()
        )

    total_tokens = input_tokens + output_tokens + cache_read + cache_creation

    today = str(date.today())
    data = _load_usage(ctx)

    if today not in data:
        data[today] = {
            "sessions": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "duration_ms": 0,
        }

    day = data[today]
    day["sessions"] += 1
    day["input_tokens"] += input_tokens
    day["output_tokens"] += output_tokens
    day["cache_read_tokens"] += cache_read
    day["cache_creation_tokens"] += cache_creation
    day["total_tokens"] += total_tokens
    day["cost_usd"] = round(day["cost_usd"] + cost_usd, 6)
    day["duration_ms"] += duration_ms

    _save_usage(ctx, data)

    logger.info(
        "[Usage] %s session: %d in + %d out + %d cache = %d total (est $%.4f)",
        ctx.name, input_tokens, output_tokens,
        cache_read + cache_creation, total_tokens, cost_usd,
    )


def get_today_usage(ctx) -> dict:
    """Get today's usage for a project."""
    data = _load_usage(ctx)
    today = str(date.today())
    return data.get(today, {
        "sessions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
    })


def get_weekly_usage(ctx) -> dict:
    """Get aggregated usage for the last 7 days."""
    data = _load_usage(ctx)
    totals = {
        "sessions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
        "days": 0,
    }

    today = date.today()
    for i in range(7):
        day_str = str(today - timedelta(days=i))
        if day_str in data:
            day = data[day_str]
            totals["sessions"] += day.get("sessions", 0)
            totals["input_tokens"] += day.get("input_tokens", 0)
            totals["output_tokens"] += day.get("output_tokens", 0)
            totals["cache_read_tokens"] += day.get("cache_read_tokens", 0)
            totals["cache_creation_tokens"] += day.get("cache_creation_tokens", 0)
            totals["total_tokens"] += day.get("total_tokens", 0)
            totals["cost_usd"] = round(totals["cost_usd"] + day.get("cost_usd", 0.0), 6)
            totals["duration_ms"] += day.get("duration_ms", 0)
            totals["days"] += 1

    return totals


def get_all_time_usage(ctx) -> dict:
    """Get total lifetime usage for a project."""
    data = _load_usage(ctx)
    totals = {
        "sessions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
        "first_day": None,
        "last_day": None,
        "active_days": 0,
    }

    for day_str in sorted(data.keys()):
        day = data[day_str]
        totals["sessions"] += day.get("sessions", 0)
        totals["input_tokens"] += day.get("input_tokens", 0)
        totals["output_tokens"] += day.get("output_tokens", 0)
        totals["total_tokens"] += day.get("total_tokens", 0)
        totals["cost_usd"] = round(totals["cost_usd"] + day.get("cost_usd", 0.0), 6)
        totals["duration_ms"] += day.get("duration_ms", 0)
        totals["active_days"] += 1
        if totals["first_day"] is None:
            totals["first_day"] = day_str
        totals["last_day"] = day_str

    return totals


def format_tokens(n: int) -> str:
    """Format token count for display: 1234567 -> 1.2M, 45000 -> 45K."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_duration(ms: int) -> str:
    """Format milliseconds to human readable: 180000 -> 3m 0s."""
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining = seconds % 60
    if minutes < 60:
        return f"{minutes}m {remaining}s"
    hours = minutes // 60
    remaining_min = minutes % 60
    return f"{hours}h {remaining_min}m"


def show_usage(ctx, period: str = "today"):
    """Print usage summary for a project.

    Args:
        ctx: ProjectContext
        period: 'today', 'week', or 'all'
    """
    if period == "today":
        u = get_today_usage(ctx)
        label = "Today"
    elif period == "week":
        u = get_weekly_usage(ctx)
        label = "Last 7 days"
    else:
        u = get_all_time_usage(ctx)
        label = "All time"

    print(f"\n  ┌─── {ctx.name} — Usage ({label}) ───")
    print(f"  │ Sessions:     {u['sessions']}")
    print(f"  │ Input:        {format_tokens(u['input_tokens'])}")
    print(f"  │ Output:       {format_tokens(u['output_tokens'])}")
    print(f"  │ Total tokens: {format_tokens(u['total_tokens'])}")
    print(f"  │ Est. cost:    ${u['cost_usd']:.4f}")
    print(f"  │ Duration:     {format_duration(u['duration_ms'])}")

    if period == "all" and u.get("active_days"):
        avg_per_day = u["total_tokens"] // max(u["active_days"], 1)
        print(f"  │ Active days:  {u['active_days']}")
        print(f"  │ Avg/day:      {format_tokens(avg_per_day)}")

    print(f"  └───")


def show_usage_all(period: str = "today"):
    """Show usage across all projects with totals."""
    from registry import list_projects, get

    projects = list_projects()
    if not projects:
        print("  No projects registered.")
        return

    grand = {
        "sessions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
    }

    if period == "today":
        label = "Today"
    elif period == "week":
        label = "Last 7 days"
    else:
        label = "All time"

    print(f"\n  ╔═══ Steel District — Usage ({label}) ═══")
    print(f"  ║")
    print(f"  ║  {'Project':<22} {'Sessions':>8} {'Tokens':>10} {'Cost':>10} {'Time':>8}")
    print(f"  ║  {'─' * 22} {'─' * 8} {'─' * 10} {'─' * 10} {'─' * 8}")

    for p in projects:
        try:
            ctx = get(p["name"])
            if period == "today":
                u = get_today_usage(ctx)
            elif period == "week":
                u = get_weekly_usage(ctx)
            else:
                u = get_all_time_usage(ctx)

            if u["sessions"] == 0:
                continue

            print(
                f"  ║  {ctx.name:<22} "
                f"{u['sessions']:>8} "
                f"{format_tokens(u['total_tokens']):>10} "
                f"${u['cost_usd']:>8.4f} "
                f"{format_duration(u['duration_ms']):>8}"
            )

            grand["sessions"] += u["sessions"]
            grand["input_tokens"] += u["input_tokens"]
            grand["output_tokens"] += u["output_tokens"]
            grand["total_tokens"] += u["total_tokens"]
            grand["cost_usd"] += u["cost_usd"]
            grand["duration_ms"] += u["duration_ms"]
        except Exception:
            pass

    print(f"  ║  {'─' * 22} {'─' * 8} {'─' * 10} {'─' * 10} {'─' * 8}")
    print(
        f"  ║  {'TOTAL':<22} "
        f"{grand['sessions']:>8} "
        f"{format_tokens(grand['total_tokens']):>10} "
        f"${grand['cost_usd']:>8.4f} "
        f"{format_duration(grand['duration_ms']):>8}"
    )
    print(f"  ║")
    print(f"  ╚═══")
