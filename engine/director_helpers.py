#!/usr/bin/env python3
"""Director helpers — pure/semi-pure functions for Telegram bot responses.

Extracted from director.py to keep both files under the 300-line limit.
These functions handle agency context building, slash commands, Claude CLI
calls, and database-backed fallback answers.
"""
import os
import sys
import subprocess
from pathlib import Path

import requests


def get_agency_context() -> str:
    """Build context string for Claude to understand the agency state."""
    try:
        from agency_db import agency_summary, get_recent_sessions
        from registry import list_projects

        summary = agency_summary()
        recent = get_recent_sessions(limit=5)
        projects = list_projects()

        ctx = f"""You are the Director of AutoAgent Agency — an autonomous AI development organization.
You manage {summary['projects']} projects with {summary['agents']} specialized agents.
You report to the operator via Telegram. Be concise, direct, no fluff.

Projects: {', '.join(p['name'] for p in projects)}
Sessions: {summary['total_sessions']} total
Agents: {summary['agents']}
Knowledge: {summary['knowledge_rules']} rules
Tasks: {summary['tasks_pending']} pending, {summary['tasks_done']} done

Recent sessions:
"""
        for s in recent:
            icon = "OK" if s["success"] else "FAIL"
            ctx += f"  #{s['session_num']} [{icon}] {s['project']} ({s['session_type']}) agent={s.get('agent') or 'generic'} summary={s.get('summary','')[:60]}\n"

        # Add recent failures for context
        failed = [s for s in get_recent_sessions(limit=20) if not s["success"]]
        if failed:
            ctx += f"\nRecent failures ({len(failed)}):\n"
            for s in failed[:5]:
                ctx += f"  #{s['session_num']} {s['project']} — {s.get('summary','no details')[:80]}\n"

        return ctx
    except Exception as e:
        return f"Agency context unavailable: {e}"


def handle_command(cmd: str) -> str:
    """Handle slash commands directly."""
    if cmd == "/status":
        try:
            from agency_db import agency_summary, get_recent_sessions
            s = agency_summary()
            recent = get_recent_sessions(limit=3)
            recent_lines = ""
            for r in recent:
                icon = "✅" if r["success"] else "❌"
                recent_lines += f"\n  {icon} #{r['session_num']} {r['project']} ({r.get('agent') or 'generic'})"
            return (
                f"📊 <b>Agency Status</b>\n\n"
                f"🏗 Projects: <b>{s['projects']}</b>\n"
                f"🔄 Sessions: <b>{s['total_sessions']}</b>\n"
                f"🤖 Agents: <b>{s['agents']}</b>\n"
                f"🧠 Knowledge: <b>{s['knowledge_rules']}</b> rules\n"
                f"📋 Tasks: <b>{s['tasks_pending']}</b> pending, <b>{s['tasks_done']}</b> done\n"
                f"💬 Messages: <b>{s['messages']}</b>"
                f"\n\n<b>Latest:</b>{recent_lines}"
            )
        except Exception as e:
            return f"Error: {e}"

    elif cmd == "/backlog":
        try:
            from registry import list_projects, get
            lines = []
            for p in list_projects():
                ctx = get(p["name"])
                bf = ctx.memory_dir / "backlog.md"
                if bf.exists():
                    items = [l.strip() for l in bf.read_text(encoding="utf-8").splitlines()
                             if l.strip().startswith("### ")][:3]
                    if items:
                        lines.append(f"\n<b>{p['name']}</b>:")
                        for item in items:
                            lines.append(f"  {item[:70]}")
            return "📋 <b>Backlogs</b>" + "\n".join(lines) if lines else "All backlogs empty."
        except Exception as e:
            return f"Error: {e}"

    elif cmd == "/deploy":
        # Ping each project's configured health_url (per-project config, no
        # hardcoded client endpoints). Projects without one show "Local only".
        from registry import list_projects, get
        lines = []
        for p in list_projects():
            try:
                url = (get(p["name"]).config or {}).get("health_url")
            except Exception:
                url = None
            if not url:
                lines.append(f"{p['name']}: Local only (not deployed)")
                continue
            try:
                resp = requests.get(url, timeout=10)
                status = "UP" if resp.status_code == 200 else f"DOWN ({resp.status_code})"
            except Exception:
                status = "UNREACHABLE"
            lines.append(f"{p['name']}: {status}")
        return "🚀 <b>Deploy Status</b>\n\n" + ("\n".join(lines) if lines else "No projects registered.")

    elif cmd == "/agents":
        try:
            from agency_db import get_top_agents
            agents = get_top_agents(limit=10)
            if not agents:
                return "No agent data yet."
            lines = ["🤖 <b>Top Agents</b>\n"]
            for a in agents:
                lines.append(f"  {a['project']}/{a['name']}: {a['total_sessions']}s, {a['success_rate']*100:.0f}%")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    elif cmd.startswith("/screenshot") or cmd.startswith("/ss"):
        from director_commands import cmd_screenshot
        return cmd_screenshot(cmd)

    elif cmd.startswith("/projects"):
        try:
            from registry import list_projects, get
            from agency_db import get_session_stats
            lines = ["🏗 <b>Projects</b>\n"]
            for p in list_projects():
                stats = get_session_stats(p["name"])
                total = stats.get("total", 0)
                success = stats.get("successes", 0) or 0
                rate = f"{success/max(total,1)*100:.0f}%" if total > 0 else "—"
                lines.append(f"  <b>{p['name']}</b> — {total} sessions, {rate} success")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    elif cmd.startswith("/new"):
        try:
            from telegram_intake import start_intake
            desc = cmd[4:].strip()
            chat_id = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
            return start_intake(chat_id, desc)
        except Exception as e:
            return f"Error starting intake: {e}"

    elif cmd == "/help":
        return (
            "🤖 <b>Director Commands</b>\n\n"
            "<b>Build</b>\n"
            "/new [idea] — Start a new project\n"
            "/run [project] — Trigger a session\n"
            "/projects — All projects overview\n\n"
            "<b>Monitor</b>\n"
            "/status — Agency overview\n"
            "/backlog — Current backlogs\n"
            "/deploy — Check deploy health\n"
            "/agents — Top performers\n"
            "/ss [project] — Take screenshots\n\n"
            "<b>Decide</b>\n"
            "/brain [question] — Ask the 4-model brain\n"
            "/council [question] — Ask the Bull/Bear/Pragmatist council\n"
            "/orchestrator [project] — See next-task routing\n"
            "/graph [project] — Task dependency analysis\n\n"
            "<b>Control</b>\n"
            "/pause — Pause cron\n"
            "/resume — Resume cron\n"
            "/help — This message\n\n"
            "Or just talk to me — I know everything about your projects."
        )

    elif cmd.startswith("/run"):
        parts = cmd.split()
        project = parts[1] if len(parts) > 1 else None
        if project:
            try:
                from director_commands import _resolve_project_name
                result = subprocess.run(
                    [sys.executable, "engine/self_improve.py", "auto", _resolve_project_name(project)],
                    cwd=str(Path(__file__).parent.parent),
                    capture_output=True, text=True, timeout=600
                )
                return f"Session complete:\n<pre>{result.stdout[-500:]}</pre>"
            except subprocess.TimeoutExpired:
                return "Session timed out (10min limit)."
            except Exception as e:
                return f"Error: {e}"
        return "Usage: /run <project_name>"

    elif cmd.startswith("/graph"):
        from director_commands import cmd_graph
        return cmd_graph(cmd)

    elif cmd.startswith("/flags"):
        from director_commands import cmd_flags
        return cmd_flags(cmd)

    elif cmd.startswith("/council"):
        from director_commands import cmd_council
        return cmd_council(cmd)

    elif cmd.startswith("/brain"):
        from director_brain import cmd_brain
        return cmd_brain(cmd)

    elif cmd.startswith("/orchestrator") or cmd.startswith("/orch"):
        from director_orchestrator import cmd_orchestrator
        return cmd_orchestrator(cmd)

    elif cmd == "/pause":
        try:
            from comms import set_paused
            set_paused(True)
            return "⏸ Agency PAUSED."
        except Exception:
            return "⏸ Pause flag set (will take effect next cron run)."

    elif cmd == "/resume":
        try:
            from comms import set_paused
            set_paused(False)
            return "▶️ Agency RESUMED."
        except Exception:
            return "▶️ Resume flag set."

    elif cmd.startswith("/wiki"):
        from director_commands import cmd_wiki
        return cmd_wiki(cmd)

    elif cmd.startswith("/red"):
        from director_commands import cmd_red
        return cmd_red(cmd)

    return f"Unknown command: {cmd}\nSend /help for options."


# Backward-compatible re-exports from director_ai
from director_ai import ask_claude, _fallback_answer  # noqa: F401
