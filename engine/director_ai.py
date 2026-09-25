#!/usr/bin/env python3
"""Director AI — Claude CLI integration and database-backed fallback answers.

Extracted from director_helpers.py to keep both files under the 300-line limit.
"""
import os
import sys
import subprocess
from pathlib import Path


def _project_names() -> list[str]:
    """Registered project names, from the registry — never a hardcoded roster.
    Empty list if the registry can't be read (fallback answers degrade to the
    all-projects query rather than crashing)."""
    try:
        from registry import list_projects
        return [p["name"] for p in list_projects()]
    except Exception:
        return []


def ask_claude(question: str) -> str:
    """Use Claude CLI to answer complex questions with full agency context."""
    from director_helpers import get_agency_context
    context = get_agency_context()
    prompt = f"""{context}

The operator is messaging you on Telegram. Respond concisely (under 300 chars if possible, max 1000). Be direct, no fluff. You have access to all project state.

Operator says: {question}

Respond:"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--max-turns", "1", "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).parent.parent),
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
        )
        response = result.stdout.strip()
        if not response:
            return _fallback_answer(question)
        # Clean up any Claude formatting artifacts
        for prefix in ["Assistant:", "Claude:", "Response:"]:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        return response[:2000]
    except subprocess.TimeoutExpired:
        return _fallback_answer(question)
    except FileNotFoundError:
        return _fallback_answer(question)
    except Exception:
        return _fallback_answer(question)


def _fallback_answer(question: str) -> str:
    """Answer questions using the agency database."""
    from director_helpers import handle_command
    q = question.lower()
    try:
        from agency_db import get_recent_sessions, agency_summary, get_agents, get_knowledge, get_tasks

        # Failure questions
        if "fail" in q or "broke" in q or "error" in q or "wrong" in q or "issue" in q:
            project = None
            for name in _project_names():
                if name.lower() in q:
                    project = name
                    break
            sessions = get_recent_sessions(project=project, limit=30)
            failed = [s for s in sessions if not s["success"]]
            if failed:
                lines = [f"<b>{len(failed)} failures</b> (last 30 sessions):\n"]
                for s in failed[:7]:
                    lines.append(f"  #{s['session_num']} <b>{s['project']}</b> ({s['session_type']}) {s.get('agent') or 'generic'}")
                    if s.get('summary'):
                        lines.append(f"    {s['summary'][:80]}")
                return "\n".join(lines)
            return "No recent failures found."

        # Agent questions
        if "agent" in q:
            if "how many" in q or "count" in q:
                s = agency_summary()
                total_agents = sum(len(get_agents(n)) for n in _project_names())
                return f"{total_agents} agents across {s['projects']} projects. {s['total_sessions']} sessions run, {s['knowledge_rules']} rules learned."
            if "top" in q or "best" in q or "perform" in q:
                return handle_command("/agents")
            if "list" in q:
                lines = ["<b>Agents by project:</b>\n"]
                for name in _project_names():
                    agents = get_agents(name)
                    if agents:
                        names = ", ".join(a["name"] for a in agents[:8])
                        lines.append(f"<b>{name}</b> ({len(agents)}): {names}")
                return "\n".join(lines)

        # Session questions
        if "session" in q or "recent" in q or "today" in q or "last" in q:
            project = None
            for name in _project_names():
                if name.lower() in q:
                    project = name
                    break
            sessions = get_recent_sessions(project=project, limit=8)
            lines = ["<b>Recent sessions:</b>\n"]
            for s in sessions:
                icon = "✅" if s["success"] else "❌"
                lines.append(f"  {icon} #{s['session_num']} {s['project']} ({s['session_type']}) {s.get('agent') or ''}")
            return "\n".join(lines)

        # Project questions
        if "project" in q or any(n.lower() in q for n in _project_names()):
            for name in _project_names():
                if name.lower() in q:
                    from agency_db import get_session_stats
                    stats = get_session_stats(name)
                    agents = get_agents(name)
                    tasks = get_tasks(name, "pending")
                    return (
                        f"<b>{name}</b>\n"
                        f"Sessions: {stats.get('total', 0)}\n"
                        f"Agents: {len(agents)}\n"
                        f"Pending tasks: {len(tasks)}\n"
                        f"Success rate: {(stats.get('successes',0) / max(stats.get('total',1),1)) * 100:.0f}%"
                    )

        # Knowledge questions
        if "know" in q or "learn" in q or "rule" in q:
            s = agency_summary()
            return f"{s['knowledge_rules']} rules across {s['projects']} projects. Rules score by recency × frequency × universality. Low-scoring rules auto-pruned."

        # What/how/status questions
        if "what" in q and ("ship" in q or "built" in q or "done" in q or "did" in q):
            sessions = get_recent_sessions(limit=10)
            done = [s for s in sessions if s["success"]]
            if done:
                lines = ["<b>Recently completed:</b>\n"]
                for s in done[:5]:
                    lines.append(f"  ✅ {s['project']} #{s['session_num']} ({s['session_type']}) {s.get('summary','')[:60]}")
                return "\n".join(lines)

        # Deploy/health questions
        if "deploy" in q or "live" in q or "up" in q or "health" in q:
            return handle_command("/deploy")

        # Greeting
        if q in ("hi", "hello", "hey", "yo", "sup"):
            s = agency_summary()
            return f"Agency status: {s['projects']} projects, {s['agents']} agents, {s['tasks_pending']} tasks pending. What do you need?"

        return "I can answer about: agents, sessions, failures, projects, deploys, backlogs, knowledge. Or try /status, /backlog, /agents, /deploy."
    except Exception as e:
        return f"Error: {e}. Try /status or /help."
