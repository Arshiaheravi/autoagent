"""Command handling + background listener for Telegram comms.

Split from comms.py to keep both files under the 300-line hard rule.
"""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _get_comms():
    """Late import to avoid circular dependency (comms ↔ comms_handlers)."""
    import comms
    return comms


# ── Command Handler ───────────────────────────────────────────────

def _handle_command(text: str):
    """Handle slash commands from the operator."""
    c = _get_comms()
    cmd = text.strip().lower().split()[0]

    if cmd == "/status":
        try:
            from registry import list_projects, get
            lines = ["📊 <b>Agency Status</b>\n"]
            for p in list_projects():
                ctx = get(p["name"])
                sessions = 0
                if ctx.sessions_file.exists():
                    try:
                        sessions = len(json.loads(ctx.sessions_file.read_text()))
                    except Exception:
                        pass
                lines.append(f"  <b>{p['name']}</b>: {sessions} sessions")
            lines.append(f"\n🔄 Auto-run: {'PAUSED' if c.is_paused() else 'ACTIVE'}")
            c._send("\n".join(lines))
        except Exception as e:
            c._send(f"Error getting status: {e}")

    elif cmd == "/backlog":
        try:
            from registry import list_projects, get
            for p in list_projects():
                ctx = get(p["name"])
                bf = ctx.memory_dir / "backlog.md"
                if bf.exists():
                    text = bf.read_text(encoding="utf-8")
                    items = [l.strip() for l in text.splitlines()
                             if l.strip().startswith("### ") or l.strip().startswith("- [ ]")][:5]
                    if items:
                        c._send(f"📋 <b>{p['name']}</b> backlog:\n" + "\n".join(f"  {i[:80]}" for i in items))
        except Exception as e:
            c._send(f"Error: {e}")

    elif cmd == "/pause":
        c.set_paused(True)
        c._send("⏸ Agency PAUSED. No autonomous sessions will run. Send /resume to restart.")

    elif cmd == "/resume":
        c.set_paused(False)
        c._send("▶️ Agency RESUMED. Autonomous sessions active.")

    elif cmd == "/help":
        c._send(
            "🤖 <b>AutoAgent Commands</b>\n\n"
            "/status — Agency status across all projects\n"
            "/backlog — Current task backlogs\n"
            "/plan — View and edit the current agent plan\n"
            "/pause — Pause autonomous sessions\n"
            "/resume — Resume autonomous sessions\n"
            "/help — This message\n\n"
            "<i>Reply to any agent message to respond directly.</i>"
        )

    elif cmd == "/plan":
        try:
            plan_path = _get_current_task_path()
            if plan_path.exists():
                from session_hooks import format_plan_message
                msg = format_plan_message(plan_path.read_text(encoding="utf-8"))
                c._send(msg if msg else "No active plan.")
            else:
                c._send("No active plan.")
        except Exception as e:
            c._send(f"Error: {e}")

    else:
        c._send(f"Unknown command: {cmd}\nSend /help for options.")


# ── Background Listener ──────────────────────────────────────────

def _get_current_task_path() -> Path:
    """Return path to the first project's current_task.md (for /plan command)."""
    try:
        from registry import list_projects, get
        projects = list_projects()
        if projects:
            ctx = get(projects[0]["name"])
            return ctx.memory_dir / "current_task.md"
    except Exception:
        pass
    return Path("memory/current_task.md")


def propose_plan(plan_path: Path, project: str = "",
                 timeout: int = 120) -> Optional[str]:
    """Send plan to Telegram for review. If user replies with edit, apply it.

    Returns the user's reply text if they edited, None if timeout/approval.
    """
    if not plan_path.exists():
        return None
    plan_text = plan_path.read_text(encoding="utf-8")
    from session_hooks import format_plan_message, parse_plan_edit
    msg = format_plan_message(plan_text)
    if not msg:
        return None
    c = _get_comms()
    reply = c.ask(
        f"{msg}\n\n<i>Reply to edit, or 'ok' to approve ({timeout}s timeout).</i>",
        project=project, timeout_seconds=timeout,
    )
    if not reply:
        return None
    updated = parse_plan_edit(plan_text, reply)
    if updated != plan_text:
        plan_path.write_text(updated, encoding="utf-8")
        c._send("✅ Plan updated.")
        return reply
    c._send("👍 Plan approved.")
    return None


# ── Background Listener ──────────────────────────────────────────

_listener_running = False


def start_listener():
    """Start background thread that listens for Telegram commands."""
    global _listener_running
    if _listener_running:
        return
    _listener_running = True
    thread = threading.Thread(target=_background_listener, daemon=True, name="telegram-listener")
    thread.start()
    logger.info("Telegram command listener started")


def _background_listener():
    """Long-poll Telegram for commands (runs in background thread)."""
    c = _get_comms()
    last_update_id = 0
    try:
        resp = requests.get(f"{c.API_BASE}/getUpdates", params={"limit": 1, "offset": -1}, timeout=c.TIMEOUT)
        data = resp.json()
        if data.get("ok") and data.get("result"):
            last_update_id = data["result"][-1]["update_id"]
    except Exception:
        pass

    while True:
        try:
            resp = requests.get(f"{c.API_BASE}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 30,
            }, timeout=35)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    if chat_id == c.CHAT_ID and text and text.startswith("/"):
                        _handle_command(text)
                    elif (chat_id == c.CHAT_ID and text and c._pending_question
                          and c._question_message_id is not None):
                        reply_to = msg.get("reply_to_message", {})
                        reply_to_id = reply_to.get("message_id") if reply_to else None
                        if reply_to_id == c._question_message_id:
                            c._reply_text = text
                            c._reply_event.set()
        except Exception:
            time.sleep(5)
