#!/usr/bin/env python3
"""Subagent spawning — isolated context for specialized tasks.

Key insight from learn-claude-code s04: "Process isolation gives context
isolation for free." Each subagent starts with a fresh message history,
preventing context bloat from the parent agent's work.

Use cases:
  - Parent agent delegates a sub-task (e.g., "write tests for X")
  - Parallel work: multiple subagents on independent tasks
  - Expertise isolation: frontend agent vs backend agent

Each subagent:
  - Gets a focused boot prompt (task + agent role only)
  - Runs in its own Claude CLI process
  - Has a turn limit (default 20, configurable)
  - Returns structured result (success, output, files changed)
"""
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from registry import ProjectContext

logger = logging.getLogger(__name__)


@dataclass
class SubagentResult:
    """Result from a subagent execution."""
    agent_name: str
    task: str
    success: bool
    output: str = ""
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    error: str = ""


def _find_claude() -> str:
    found = shutil.which("claude")
    if found:
        return found
    if sys.platform == "win32":
        npm_bin = os.path.join(os.environ.get("APPDATA", ""), "npm")
        win_path = os.path.join(npm_bin, "claude.cmd")
        if os.path.exists(win_path):
            return win_path
    return "claude"


def build_subagent_prompt(task: str, agent_name: Optional[str],
                          ctx: ProjectContext, parent_context: str = "") -> str:
    """Build a focused prompt for a subagent.

    Minimal context: just the task + agent role. No backlog, no activity log,
    no memory — the subagent is a clean-room worker.
    """
    from orchestrator import build_agent_boot_prompt

    # Start with agent boot prompt (includes role + skills)
    boot = build_agent_boot_prompt(ctx, agent_name, "work")

    # Add focused task instruction
    boot += f"""

--- SUBAGENT TASK ---
You are a subagent spawned for a specific task. Complete it and stop.

Task: {task}

{f"Context from parent agent: {parent_context}" if parent_context else ""}

Rules:
- Complete ONLY this task — nothing else
- Do not read backlog.md or pick new tasks
- Do not update activity_log.md or knowledge.md
- Run tests after making changes
- If tests pass, commit with prefix "agent: <what you did>"
- If you cannot complete the task, output BLOCKED: <reason> and stop
--- END SUBAGENT TASK ---
"""
    return boot


def spawn_subagent(ctx: ProjectContext, task: str,
                   agent_name: Optional[str] = None,
                   max_turns: int = 20,
                   timeout_seconds: int = 600,
                   working_dir: Optional[Path] = None,
                   parent_context: str = "") -> SubagentResult:
    """Spawn an isolated subagent to complete a specific task.

    The subagent runs in its own Claude CLI process with a fresh
    message history. Returns structured result.
    """
    claude = _find_claude()
    cwd = str(working_dir or ctx.project_root)
    prompt = build_subagent_prompt(task, agent_name, ctx, parent_context)

    start = datetime.now()
    try:
        result = subprocess.run(
            [claude, "-p", prompt,
             "--output-format", "stream-json",
             "--dangerously-skip-permissions",
             "--max-turns", str(max_turns)],
            cwd=cwd,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout_seconds,
        )

        duration = (datetime.now() - start).total_seconds()
        output_lines = []
        files_changed = []
        cost = 0.0

        # Parse stream-json output
        for raw in result.stdout.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
                t = ev.get("type", "")
                if t == "assistant":
                    for block in ev.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            output_lines.append(block["text"].strip())
                        elif block.get("type") == "tool_use":
                            name = block.get("name", "")
                            inp = block.get("input", {})
                            if name in ("Write", "Edit"):
                                fp = inp.get("file_path", "")
                                if fp and fp not in files_changed:
                                    files_changed.append(fp)
                elif t == "result":
                    cost = ev.get("cost_usd") or ev.get("total_cost_usd") or 0.0
            except (json.JSONDecodeError, Exception):
                if raw and not raw.startswith("{"):
                    output_lines.append(raw)

        return SubagentResult(
            agent_name=agent_name or "generic",
            task=task,
            success=result.returncode == 0,
            output="\n".join(output_lines[-20:]),  # last 20 lines
            files_changed=files_changed,
            duration_seconds=duration,
            cost_usd=cost if isinstance(cost, (int, float)) else 0.0,
        )

    except subprocess.TimeoutExpired:
        return SubagentResult(
            agent_name=agent_name or "generic",
            task=task,
            success=False,
            error=f"Subagent timed out after {timeout_seconds}s",
            duration_seconds=timeout_seconds,
        )
    except Exception as e:
        return SubagentResult(
            agent_name=agent_name or "generic",
            task=task,
            success=False,
            error=str(e),
            duration_seconds=(datetime.now() - start).total_seconds(),
        )


def spawn_parallel_subagents(ctx: ProjectContext,
                             tasks: list[dict],
                             max_concurrent: int = 2) -> list[SubagentResult]:
    """Spawn multiple subagents in parallel using worktrees.

    Each task dict has: {"task": str, "agent": str|None}
    Uses git worktrees so agents don't conflict.

    Note: On a single machine, max_concurrent is limited by CPU and
    Claude CLI's single-session constraint. This is designed for when
    that constraint is lifted (cloud execution, multiple API keys).
    For now, runs sequentially with worktree isolation.
    """
    from worktree import create_worktree, merge_worktree, cleanup_worktree

    results = []
    for i, task_def in enumerate(tasks):
        task_text = task_def.get("task", "")
        agent = task_def.get("agent")
        session_num = task_def.get("session_num", 9000 + i)

        # Create isolated worktree
        ws = create_worktree(ctx.project_root, agent or "generic", session_num)
        working_dir = ws.worktree_dir if ws else None

        # Spawn subagent in worktree
        result = spawn_subagent(
            ctx, task_text,
            agent_name=agent,
            working_dir=working_dir,
        )
        results.append(result)

        # Merge and cleanup worktree
        if ws:
            if result.success:
                merge_worktree(ws, ctx.project_root)
            cleanup_worktree(ws, ctx.project_root)

    return results
