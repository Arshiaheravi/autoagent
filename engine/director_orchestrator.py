#!/usr/bin/env python3
"""Terminal/Director helpers for querying the orchestrator."""


def _is_operator_only(task_name: str) -> bool:
    lowered = task_name.lower()
    # "seb action" kept for backward compat with existing backlogs.
    markers = ("needs-human", "needs human", "human action", "seb action", "blocked")
    return any(m in lowered for m in markers)


def _current_task_summary(ctx) -> tuple[str | None, str | None]:
    """Extract a readable task + agent summary from current_task.md."""
    current = ctx.memory_dir / "current_task.md"
    if not current.exists():
        return None, None

    text = current.read_text(encoding="utf-8").strip()
    if not text or "no current task" in text.lower():
        return None, None

    task = None
    agent = None
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("TASK:"):
            task = stripped.split(":", 1)[1].strip()
        elif upper.startswith("AGENT:"):
            agent = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("# Current Task:"):
            task = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- [ ]") and not task:
            task = stripped[5:].strip()

    if not task:
        task = text.splitlines()[0].lstrip("# ").strip()
    if agent and agent.lower() in ("none", "(none)", "n/a", "-"):
        agent = None
    return task, agent


def cmd_orchestrator(cmd: str) -> str:
    parts = cmd.split(maxsplit=1)
    project = parts[1].strip() if len(parts) > 1 else None
    if not project:
        return "Usage: /orchestrator <project_name>"
    try:
        from registry import get
        from agent_index import auto_route
        from orchestrator import get_ready_tasks
        from director_commands import _resolve_project_name

        ctx = get(_resolve_project_name(project))
        current_task, current_agent = _current_task_summary(ctx)
        ready = [task for task in get_ready_tasks(ctx) if not _is_operator_only(task["name"])]

        if not ready:
            backlog = ctx.memory_dir / "backlog.md"
            if backlog.exists():
                for line in backlog.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("### "):
                        name = stripped[4:].strip()
                        if _is_operator_only(name):
                            continue
                        ready = [{"name": name, "agent_hint": None}]
                        break
                    if stripped.startswith("- [ ]"):
                        name = stripped[5:].strip()
                        if _is_operator_only(name):
                            continue
                        ready = [{"name": name, "agent_hint": None}]
                        break

        next_task = ready[0]["name"] if ready else None
        next_agent = ready[0].get("agent_hint") if ready else None
        if next_task and not next_agent:
            next_agent = auto_route(ctx, next_task)

        lines = [f"\U0001f3bc <b>Orchestrator \u2014 {ctx.name}</b>\n"]
        lines.append(f"<b>Current:</b> {current_task[:180]}{f' ({current_agent})' if current_agent else ''}" if current_task else "<b>Current:</b> idle")
        if next_task:
            lines.append(f"<b>Next:</b> {next_task[:180]}")
            lines.append(f"<b>Route:</b> {next_agent or 'generic'}")
        else:
            lines.append("<b>Next:</b> no ready tasks")

        if ready:
            lines.append("\n<b>Ready now:</b>")
            for task in ready[:5]:
                hint = task.get("agent_hint") or auto_route(ctx, task["name"]) or "generic"
                lines.append(f"  - {task['name'][:140]} [{hint}]")
        return "\n".join(lines)
    except Exception as e:
        return f"Orchestrator failed: {e}"
