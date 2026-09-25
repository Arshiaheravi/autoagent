#!/usr/bin/env python3
"""Notification Filter — triage, rewrite, and batch outbound bot messages.

Three tiers:
  IMMEDIATE  — sends now, rewritten in human language (failures, questions, deploys down)
  BATCH      — queued for morning/evening digest (session completions, insights, info)
  SILENT     — dropped entirely (no-op sessions, repeated localhost errors, status spam)

Usage (called from comms.py wrappers):
    from notification_filter import classify, rewrite_immediate, queue_for_digest, get_todays_batch
"""
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

AUTOAGENT_ROOT = Path(__file__).parent.parent
NOTIFICATIONS_DIR = AUTOAGENT_ROOT / "brain" / "notifications"
NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)

# Noise patterns — never send these
_SILENT_PATTERNS = [
    r"no current task",
    r"# no current task",
    r"0 done, 0 remaining",
    r"localhost:\d+",           # connection refused to localhost
    r"err_connection_refused",
    r"session #\d+ \(work\).{0,30}$",  # bare session complete with no substance
]

# Immediate patterns — always send now
_IMMEDIATE_PATTERNS = [
    r"question",
    r"escalat",
    r"deploy.*fail",
    r"crash",
    r"exception",
    r"critical",
    r"unreachable",
    r"down\b",
]


def _today_file() -> Path:
    return NOTIFICATIONS_DIR / f"{date.today().isoformat()}.json"


def queue_for_digest(event_type: str, raw_message: str, summary: str = "") -> None:
    """Add an event to today's batch file."""
    entry = {
        "time": datetime.now().strftime("%H:%M"),
        "type": event_type,
        "raw": raw_message[:300],
        "summary": summary or raw_message[:150],
    }
    path = _today_file()
    batch = []
    if path.exists():
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            batch = []
    batch.append(entry)
    path.write_text(json.dumps(batch, indent=2), encoding="utf-8")


def get_todays_batch() -> list[dict]:
    """Return today's batched notification events."""
    path = _today_file()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def classify(event_type: str, message: str) -> str:
    """Return 'immediate', 'batch', or 'silent' for a notification.

    event_type: 'session', 'notify', 'escalate', 'ask', 'deploy', 'insight', 'visual_check'
    """
    msg_lower = message.lower()

    # Hard rules first
    if event_type in ("escalate", "ask"):
        return "immediate"

    for pattern in _SILENT_PATTERNS:
        if re.search(pattern, msg_lower):
            return "silent"

    for pattern in _IMMEDIATE_PATTERNS:
        if re.search(pattern, msg_lower):
            return "immediate"

    # Session completions: only immediate if failed
    if event_type == "session":
        if "fail" in msg_lower or "error" in msg_lower or "❌" in message:
            return "immediate"
        return "batch"

    # Deploy: immediate if failed, batch if success
    if event_type == "deploy":
        if "fail" in msg_lower or "💥" in message:
            return "immediate"
        return "batch"

    # Visual check errors: batch (not immediate — usually localhost noise)
    if event_type == "visual_check":
        return "batch"

    # Default: batch FYI messages, don't spam
    return "batch"


def rewrite_immediate(event_type: str, raw_message: str) -> str:
    """Rewrite a notification in plain human language using Claude.

    Only called for IMMEDIATE tier — batch items get rewritten at digest time.
    Keeps it tight: one or two sentences max.
    """
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=(
                "You rewrite automated system notifications as plain, direct messages "
                "from a smart assistant to a technical founder. "
                "One or two sentences. No emojis. No markdown. No preamble. "
                "Lead with what happened and what (if anything) needs doing."
            ),
            messages=[{"role": "user", "content": f"Rewrite this notification:\n\n{raw_message}"}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("Rewrite failed, using raw: %s", e)
        return raw_message
