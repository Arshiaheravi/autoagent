#!/usr/bin/env python3
"""Director Intelligence — conversational Claude layer for the Telegram bot.

Replaces the dumb _fallback_answer() with a real Claude SDK call that has full
agency context. Maintains short-term conversation history so follow-up questions
work naturally. Reads projects, sessions, backlog, failures, and distilled knowledge
to answer anything the operator asks about the agency.

Usage:
    from director_intelligence import respond, clear_history
    reply = respond("what happened with myapp today?")
"""
import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

AUTOAGENT_ROOT = Path(__file__).parent.parent
BRAIN_DIR = AUTOAGENT_ROOT / "brain"
DISTILLED_PATH = BRAIN_DIR / "distilled.md"

# Short-term conversation history — resets on director restart, that's fine
_history: list[dict] = []
MAX_HISTORY_TURNS = 12  # 6 exchanges


def clear_history():
    """Clear conversation history (e.g. after long idle period)."""
    global _history
    _history = []


def _build_agency_context() -> str:
    """Gather live agency state to ground Claude's responses."""
    lines = [f"Today is {datetime.now().strftime('%A, %B %d %Y — %H:%M')}."]

    try:
        from agency_db import agency_summary, get_recent_sessions
        s = agency_summary()
        lines.append(
            f"Agency: {s['projects']} projects, {s['total_sessions']} sessions total, "
            f"{s['tasks_pending']} tasks pending, {s['knowledge_rules']} knowledge rules."
        )
        recent = get_recent_sessions(limit=10)
        if recent:
            lines.append("\nRecent sessions:")
            for r in recent:
                status = "OK" if r["success"] else "FAILED"
                agent = r.get("agent") or "generic"
                summary = (r.get("summary") or "")[:80]
                lines.append(
                    f"  #{r['session_num']} {r['project']} ({r['session_type']}) "
                    f"[{agent}] {status} — {summary}"
                )
        failed = [r for r in (get_recent_sessions(limit=30) or []) if not r["success"]]
        if failed:
            lines.append(f"\nRecent failures ({len(failed)} in last 30 sessions):")
            for r in failed[:5]:
                lines.append(f"  #{r['session_num']} {r['project']} — {(r.get('summary') or 'no details')[:80]}")
    except Exception as e:
        lines.append(f"(DB unavailable: {e})")

    try:
        from registry import list_projects, get
        lines.append("\nProjects:")
        for p in list_projects():
            ctx = get(p["name"])
            backlog_items = []
            bf = ctx.memory_dir / "backlog.md"
            if bf.exists():
                backlog_items = [
                    l.strip() for l in bf.read_text(encoding="utf-8").splitlines()
                    if l.strip().startswith("### ")
                ][:3]
            backlog_str = ", ".join(i.replace("### ", "") for i in backlog_items) or "empty"
            lines.append(f"  {p['name']}: backlog → {backlog_str}")
    except Exception:
        pass

    # Last 40 lines of distilled knowledge
    if DISTILLED_PATH.exists():
        tail = DISTILLED_PATH.read_text(encoding="utf-8").splitlines()[-40:]
        if tail:
            lines.append("\nRecently distilled knowledge:")
            lines.append("\n".join(tail))

    # Today's batched notifications
    try:
        from notification_filter import get_todays_batch
        batch = get_todays_batch()
        if batch:
            lines.append(f"\nToday's activity ({len(batch)} events):")
            for item in batch[-15:]:
                lines.append(f"  [{item['type']}] {item['summary']}")
    except Exception:
        pass

    return "\n".join(lines)


SYSTEM_PROMPT = """You are the Director — an intelligent agent managing the operator's autonomous AI development agency (AutoAgent / Autoagency).

The operator communicates with you via Telegram — a technical founder running multiple AI products, fast-moving, wants terse answers, no fluff. Talk to them like a smart colleague who's been watching the agency all day.

Your job:
- Answer questions about what's happening across all projects
- Give honest assessments — if something's broken, say so directly
- Help them prioritize (what needs attention vs what can wait)
- Distill complex agency state into clear, actionable insight
- Remember what they said earlier in this conversation

Style rules:
- Plain English, no Telegram formatting markup in body text (bold/italic sparingly)
- Lead with the answer, not the context
- Short paragraphs or bullet points for complex answers
- If something needs action, say what it is
- Don't repeat information they already know from earlier in the thread
- Don't sign off or add pleasantries
- Max 3-4 sentences for simple questions, more only if they ask for depth"""


def respond(user_message: str) -> str:
    """Generate a conversational response with full agency context.

    Maintains conversation history across calls within the same director session.
    """
    global _history

    agency_ctx = _build_agency_context()
    full_system = f"{SYSTEM_PROMPT}\n\n--- LIVE AGENCY STATE ---\n{agency_ctx}"

    # Append user message to history
    _history.append({"role": "user", "content": user_message})

    # Trim to max turns (keep most recent)
    if len(_history) > MAX_HISTORY_TURNS * 2:
        _history = _history[-(MAX_HISTORY_TURNS * 2):]

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=512,
            system=full_system,
            messages=_history,
        )
        reply = response.content[0].text.strip()
        # Add assistant reply to history
        _history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error("Intelligence layer failed: %s", e)
        # Remove the user message we added since we can't respond
        _history.pop()
        return f"Something went wrong on my end: {e}"
