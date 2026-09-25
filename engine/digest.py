#!/usr/bin/env python3
"""Digest — morning and evening summaries for the Telegram bot.

Pulls today's batched notifications, recent sessions, and backlog state,
then uses Claude to write a natural coles-notes summary. Sent at 8am and 10pm
by the director main loop.

Usage:
    from digest import morning_digest, evening_digest
    text = morning_digest()   # call once at 8am
    text = evening_digest()   # call once at 10pm
"""
import logging
import os
from datetime import datetime, date, timedelta
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

AUTOAGENT_ROOT = Path(__file__).parent.parent


def _gather_context(since_hours: int = 12) -> str:
    """Build a data dump of recent agency activity for Claude to summarize."""
    lines = [f"Date: {datetime.now().strftime('%A, %B %d %Y — %H:%M')}"]

    # Recent sessions
    try:
        from agency_db import get_recent_sessions
        sessions = get_recent_sessions(limit=20)
        if sessions:
            lines.append(f"\nSessions in last ~{since_hours}h:")
            for s in sessions:
                status = "shipped" if s["success"] else "FAILED"
                agent = s.get("agent") or "generic"
                summary = (s.get("summary") or "")[:100]
                lines.append(f"  #{s['session_num']} {s['project']} [{agent}] {status} — {summary}")
    except Exception:
        pass

    # Backlog state per project
    try:
        from registry import list_projects, get
        lines.append("\nCurrent backlogs:")
        for p in list_projects():
            ctx = get(p["name"])
            bf = ctx.memory_dir / "backlog.md"
            if bf.exists():
                items = [
                    l.strip().replace("### ", "").replace("- [ ] ", "")
                    for l in bf.read_text(encoding="utf-8").splitlines()
                    if l.strip().startswith("### ") or l.strip().startswith("- [ ]")
                ][:5]
                count = len(items)
                top = items[0] if items else "empty"
                lines.append(f"  {p['name']}: {count} tasks, top → {top[:80]}")
    except Exception:
        pass

    # Today's batched notifications
    try:
        from notification_filter import get_todays_batch
        batch = get_todays_batch()
        if batch:
            lines.append(f"\nToday's events ({len(batch)} total):")
            for item in batch:
                lines.append(f"  {item['time']} [{item['type']}] {item['summary'][:100]}")
    except Exception:
        pass

    return "\n".join(lines)


def _call_claude(system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


_DIGEST_SYSTEM = """You write short agency digests for the technical founder who runs an autonomous AI development agency.

Style:
- Coles notes — dense, useful, no padding
- Plain English, no emojis, no markdown formatting
- Lead with what matters: what shipped, what broke, what needs attention
- If nothing notable happened, say so in one line
- 4-8 lines max
- Don't use bullet points — write in short punchy sentences or fragments
- No sign-off, no greeting"""


def morning_digest() -> str:
    """What happened overnight + what's on deck today."""
    ctx = _gather_context(since_hours=10)
    prompt = (
        f"Write the morning digest. Cover: what happened overnight, "
        f"any failures or issues to know about, and what the top priorities are today.\n\n"
        f"Agency data:\n{ctx}"
    )
    try:
        return _call_claude(_DIGEST_SYSTEM, prompt)
    except Exception as e:
        logger.error("Morning digest failed: %s", e)
        return "Morning digest unavailable."


def evening_digest() -> str:
    """What shipped today + any open issues going into tomorrow."""
    ctx = _gather_context(since_hours=14)
    prompt = (
        f"Write the evening digest. Cover: what shipped today, any failures or regressions, "
        f"and what's queued for overnight.\n\n"
        f"Agency data:\n{ctx}"
    )
    try:
        return _call_claude(_DIGEST_SYSTEM, prompt)
    except Exception as e:
        logger.error("Evening digest failed: %s", e)
        return "Evening digest unavailable."
