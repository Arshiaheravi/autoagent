#!/usr/bin/env python3
"""Agency Communication System — Telegram bridge to human-in-the-loop.

Agents: notify / ask / escalate / share_insight.
Human: reply to any message, /status /backlog /pause /resume.
"""
import json
import logging
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

if not BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram notifications disabled")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEOUT = 15

# Pause flag — agents check this before running
_PAUSED = False
_pause_lock = threading.Lock()


def is_paused() -> bool:
    with _pause_lock:
        return _PAUSED


def set_paused(paused: bool):
    global _PAUSED
    with _pause_lock:
        _PAUSED = paused


# ── Send Messages ─────────────────────────────────────────────────

def _send(text: str, parse_mode: str = "HTML", reply_markup: dict = None) -> Optional[int]:
    """Send a Telegram message. Returns message_id (int) on success, None on failure."""
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": text[:4096],
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=TIMEOUT)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", {}).get("message_id")
        return None
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return None


def send_photo(photo_path: str, caption: str = "") -> bool:
    """Send a screenshot/image via Telegram."""
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(f"{API_BASE}/sendPhoto", data={
                "chat_id": CHAT_ID,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            }, files={"photo": f}, timeout=30)
        return resp.json().get("ok", False)
    except Exception as e:
        logger.warning("Photo send failed: %s", e)
        return False


def send_with_buttons(text: str, buttons: list[list[dict]]) -> bool:
    """Send a message with inline keyboard buttons.

    buttons format: [[{"text": "Label", "callback_data": "action"}], ...]
    """
    return _send(text, reply_markup={"inline_keyboard": buttons}) is not None


def notify(message: str, project: str = "", agent: str = "") -> bool:
    """Send a status notification — filtered and rewritten before sending."""
    raw = f"[{project}] ({agent}) {message}" if project else message
    try:
        from notification_filter import classify, rewrite_immediate, queue_for_digest
        tier = classify("notify", raw)
        if tier == "silent":
            return True
        if tier == "batch":
            queue_for_digest("notify", raw, summary=f"{project}: {message[:100]}" if project else message[:100])
            return True
        # immediate — rewrite and send
        human = rewrite_immediate("notify", raw)
        return _send(human) is not None
    except Exception:
        return _send(raw[:500]) is not None


def escalate(issue: str, project: str = "", agent: str = "") -> bool:
    """Send an urgent alert — always immediate, always rewritten."""
    raw = f"{project}: {issue}" if project else issue
    try:
        from notification_filter import rewrite_immediate
        human = rewrite_immediate("escalate", raw)
        return _send(f"Needs your attention — {human}\n\n<i>Reply to respond.</i>") is not None
    except Exception:
        return _send(f"Escalation — {raw}\n\n<i>Reply to respond.</i>") is not None


def share_insight(insight: str, project: str = "", agent: str = "") -> bool:
    """Queue an insight for the digest — never spams in real time."""
    raw = f"{project}: {insight}" if project else insight
    try:
        from notification_filter import queue_for_digest
        queue_for_digest("insight", raw, summary=raw[:120])
    except Exception:
        pass
    return True


def session_complete(project: str, session_num: int, session_type: str,
                     success: bool, agent: str = "", summary: str = "",
                     screenshot_path: str = "") -> bool:
    """Notify session completion — failures go immediately, successes go to digest."""
    raw = f"{project} session #{session_num} ({session_type}) agent={agent} — {summary or 'done'}"
    try:
        from notification_filter import classify, rewrite_immediate, queue_for_digest
        tier = classify("session", raw)
        if tier == "silent":
            return True
        if tier == "batch":
            queue_for_digest(
                "session", raw,
                summary=f"{project}: {'shipped' if success else 'failed'} — {(summary or '')[:80]}"
            )
            return True
        # immediate (failure)
        human = rewrite_immediate("session", raw)
        _send(human)
    except Exception:
        icon = "✅" if success else "❌"
        _send(f"{icon} {project} #{session_num} — {summary[:150] if summary else 'done'}")

    # Screenshot only on failures or explicit request — not every session
    if screenshot_path and not success:
        send_photo(screenshot_path, f"{project} session #{session_num}")
    return True


def deploy_status(project: str, status: str, url: str = "") -> bool:
    """Notify deploy status — failures immediate, successes batched."""
    raw = f"{project} deploy {status}{' — ' + url if url else ''}"
    try:
        from notification_filter import classify, rewrite_immediate, queue_for_digest
        tier = classify("deploy", raw)
        if tier == "batch":
            queue_for_digest("deploy", raw, summary=raw[:100])
            return True
        human = rewrite_immediate("deploy", raw)
        return _send(human) is not None
    except Exception:
        icon = "🚀" if status == "SUCCESS" else "💥"
        return _send(f"{icon} {project} deploy: {status}") is not None


# ── Ask & Wait for Reply ──────────────────────────────────────────

_pending_question: Optional[dict] = None
_question_message_id: Optional[int] = None
_reply_event = threading.Event()
_reply_text: str = ""


def ask(question: str, project: str = "", agent: str = "",
        timeout_seconds: int = 300) -> Optional[str]:
    """Send a question and wait for the operator's reply (up to timeout).

    Returns the reply text, or None if timeout.
    Only accepts replies that are threaded to the specific question message
    (reply_to_message_id must match), preventing wrong-message routing.
    """
    global _pending_question, _question_message_id, _reply_text
    if not BOT_TOKEN or CHAT_ID == 0:
        return None

    prefix = "❓ <b>QUESTION</b>\n"
    if project:
        prefix += f"Project: <b>{project}</b>\n"
    if agent:
        prefix += f"Agent: <i>{agent}</i>\n"

    msg_id = _send(f"{prefix}\n{question}\n\n<i>Reply within {timeout_seconds // 60}min...</i>")
    if msg_id is None:
        return None

    _pending_question = {"question": question, "project": project, "agent": agent}
    _question_message_id = msg_id
    _reply_event.clear()
    _reply_text = ""

    # Start polling for reply in background
    poll_thread = threading.Thread(target=_poll_for_reply, daemon=True)
    poll_thread.start()

    # Wait for reply or timeout
    got_reply = _reply_event.wait(timeout=timeout_seconds)
    _pending_question = None
    _question_message_id = None

    if got_reply and _reply_text:
        return _reply_text
    return None


def _poll_for_reply():
    """Poll Telegram for new messages (replies to questions).

    Only accepts messages that are threaded replies to the specific question
    (reply_to_message.message_id == _question_message_id). This prevents
    unrelated messages from being routed as answers to the wrong question.
    """
    global _reply_text
    last_update_id = 0

    # Get current update_id to skip old messages
    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params={"limit": 1, "offset": -1}, timeout=TIMEOUT)
        data = resp.json()
        if data.get("ok") and data.get("result"):
            last_update_id = data["result"][-1]["update_id"]
    except Exception:
        pass

    for _ in range(60):  # Poll for up to 5 min (60 × 5s)
        if _pending_question is None:
            break
        try:
            resp = requests.get(f"{API_BASE}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 5,
            }, timeout=10)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    # Only accept replies threaded to the question message
                    reply_to = msg.get("reply_to_message", {})
                    reply_to_id = reply_to.get("message_id") if reply_to else None

                    if (chat_id == CHAT_ID and text and not text.startswith("/")
                            and reply_to_id == _question_message_id
                            and _question_message_id is not None):
                        _reply_text = text
                        _reply_event.set()
                        _send("✅ Got it. Passing your reply back to the agent.")
                        return

                    # Handle commands
                    if chat_id == CHAT_ID and text and text.startswith("/"):
                        _handle_command(text)
        except Exception:
            pass
        time.sleep(1)


# ── Backward-compatible re-exports (split to comms_handlers.py) ──
from comms_handlers import _handle_command, start_listener, _background_listener  # noqa: F401


# ── Quick test CLI ────────────────────────────────────────────────
# Usage: python3 comms.py test   — send notify + session_complete
#        python3 comms.py listen — run the Telegram listener
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "test":
        print("Sent:", notify("Agency comms test — all systems operational.", project="AutoAgent"))
        session_complete("myapp", 200, "WORK", True, agent="coder", summary="Quick test")
    elif cmd == "listen":
        _send("🤖 Agency listener started. Send /help for commands.")
        start_listener()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: pass
