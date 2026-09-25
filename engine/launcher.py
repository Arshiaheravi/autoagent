"""
Self-healing session launcher — wraps run_session with retry logic.

When a WORK session fails (tests red, constraint violation, crash),
the launcher runs a short repair session to diagnose and fix, then retries.

Supports parallel execution: launch_parallel() runs multiple independent
tasks simultaneously using git worktrees for isolation.

Pure functions: build_repair_prompt (str in, str out).
Orchestrator: launch_with_retry (injectable run_fn for testing).
"""
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from registry import ProjectContext
from retry import should_retry, read_last_error

logger = logging.getLogger(__name__)

_MAX_FAILURE_CHARS = 3000


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


def build_repair_prompt(failure_reason: str, session_num: int,
                        project_name: str) -> str:
    """Build a focused prompt for Claude to diagnose and fix a session failure.

    Pure function: strings in, string out. No I/O.
    """
    # Truncate long failure reasons to prevent prompt bloat
    truncated = failure_reason[:_MAX_FAILURE_CHARS]

    return f"""You are fixing a failed session for project '{project_name}'.

## What happened
Session #{session_num} failed with this error:
{truncated}

## Your task
1. Read .autoagent/memory/current_task.md to understand what was being worked on
2. Run `git diff` to see what changes were made
3. Run the test command from .autoagent/PROJECT.md to see which tests fail
4. Fix the failing tests or constraint violations with minimal changes
5. Do NOT start new work — only fix what broke
6. Run tests again to verify they pass
7. If tests pass, commit the fix with prefix "agent: fix — <what you fixed>"

## Rules
- Fix ONLY what caused the failure — nothing else
- Do not refactor, clean up, or improve surrounding code
- If you cannot identify the root cause after 2 attempts, write BLOCKED to .autoagent/memory/current_task.md and stop
"""


def _iso_week_key() -> str:
    from datetime import date as _date
    y, w, _ = _date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _healer_budget_state(ctx: ProjectContext) -> tuple[float, float, float]:
    """Return (weekly_spent, weekly_cap, per_attempt_estimate) USD."""
    cap = float(ctx.config.get("healer_weekly_usd", 75.0))
    est = float(ctx.config.get("healer_attempt_estimate_usd", 1.50))
    spent = 0.0
    hw = ctx.project_home / "healer_weekly.json"
    if hw.exists():
        try:
            import json as _j
            data = _j.loads(hw.read_text(encoding="utf-8"))
            spent = float(data.get(_iso_week_key(), 0.0))
        except Exception:
            pass
    return spent, cap, est


def _healer_budget_ok(ctx: ProjectContext) -> tuple[bool, str]:
    spent, cap, est = _healer_budget_state(ctx)
    if spent + est > cap:
        return False, f"healer weekly ${spent:.2f} + ${est:.2f} est > ${cap:.2f} cap"
    return True, f"healer weekly ${spent:.2f} / ${cap:.2f}"


def _healer_log_attempt(ctx: ProjectContext):
    import json as _j
    _, _, est = _healer_budget_state(ctx)
    hw = ctx.project_home / "healer_weekly.json"
    data = {}
    if hw.exists():
        try:
            data = _j.loads(hw.read_text(encoding="utf-8"))
        except Exception:
            pass
    key = _iso_week_key()
    data[key] = round(float(data.get(key, 0.0)) + est, 2)
    hw.write_text(_j.dumps(data, indent=2))


def run_repair_session(ctx: ProjectContext, failure_reason: str,
                       session_num: int) -> bool:
    """Run a short Claude session to fix the failure.

    Returns True if the repair session completed successfully (exit 0).
    Gated on weekly healer budget (config: healer_weekly_usd, default $75).
    """
    ok, status = _healer_budget_ok(ctx)
    if not ok:
        logger.warning("Repair session skipped: %s", status)
        print(f"  [Launcher] {status} — skipping heal. Raise healer_weekly_usd to continue.")
        return False
    print(f"  [Launcher] {status}")
    _healer_log_attempt(ctx)

    claude = _find_claude()
    prompt = build_repair_prompt(failure_reason, session_num, ctx.name)

    try:
        result = subprocess.run(
            [claude, "-p", prompt,
             "--output-format", "stream-json",
             "--dangerously-skip-permissions",
             "--max-turns", "20"],
            cwd=str(ctx.project_root),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=600,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def _log_heal(ctx: ProjectContext, session_num: int, attempt: int,
              failure_reason: str, repaired: bool):
    """Append a heal attempt to memory/self_heal_log.md."""
    heal_log = ctx.memory_dir / "self_heal_log.md"
    status = "REPAIRED" if repaired else "FAILED"
    entry = (
        f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — "
        f"Session #{session_num} — Attempt {attempt} — {status}\n"
        f"Failure: {failure_reason[:500]}\n"
    )
    existing = ""
    if heal_log.exists():
        existing = heal_log.read_text(encoding="utf-8")
    heal_log.write_text(existing + entry, encoding="utf-8")


def _get_fallback_agent(current_agent: str | None, ctx) -> str | None:
    """Get next agent in fallback chain: specialist → architect → generic."""
    if current_agent and current_agent != "architect":
        # Try architect as a broad-capability fallback
        if (ctx.agents_dir / "architect.md").exists():
            return "architect"
    # Already tried architect or no architect available → go generic
    return None


def launch_with_retry(ctx: ProjectContext, session_type: str,
                      session_num: int, run_fn=None,
                      max_retries: int = 2) -> bool:
    """Run a session with agent-aware retry and fallback chain.

    Failure cascade:
      1. Run with assigned agent
      2. If fails → run repair session (fixes test failures)
      3. If repair fails → retry with architect agent (broad capability)
      4. If architect fails → retry generic (no agent scoping)
      5. If all fail → log BLOCKED, return False

    Args:
        ctx: Project context.
        session_type: work, meta, brain, deep.
        session_num: Current session number.
        run_fn: Callable(ctx, session_type, session_num, **kw) -> bool.
        max_retries: Max repair attempts per agent tier.
    """
    if run_fn is None:
        from run import run_session
        run_fn = run_session

    # First attempt (with auto-detected agent)
    success = run_fn(ctx, session_type, session_num)
    if success:
        return True

    # Rate-limit backoff: retry with exponential wait before escalating
    last_err = read_last_error(ctx.memory_dir)
    for attempt in range(3):
        do_retry, wait = should_retry(1, attempt, last_err)
        if not do_retry:
            break
        print(f"  [Launcher] Rate limit detected — waiting {wait}s (attempt {attempt + 1}/3)...")
        time.sleep(wait)
        success = run_fn(ctx, session_type, session_num)
        if success:
            return True
        last_err = read_last_error(ctx.memory_dir)

    # Only retry work sessions with repair
    if session_type != "work":
        return False

    # Repair attempt
    failure_reason = (
        f"Session #{session_num} ({session_type}) failed. "
        f"Likely cause: tests red or constraint violation after code changes."
    )
    print(f"  [Launcher] Session failed — running repair...")
    repaired = run_repair_session(ctx, failure_reason, session_num)
    _log_heal(ctx, session_num, 1, failure_reason, repaired)

    success = run_fn(ctx, session_type, session_num)
    if success:
        print(f"  [Launcher] Repair succeeded.")
        return True

    # Agent fallback chain: try architect, then generic
    try:
        from session_helpers import _detect_agent
        original_agent = _detect_agent(ctx, session_type)
    except Exception:
        original_agent = None

    fallback = _get_fallback_agent(original_agent, ctx)
    while fallback is not None or (original_agent is not None):
        agent_label = fallback or "(generic)"
        print(f"  [Launcher] Trying fallback agent: {agent_label}...")

        try:
            from agent_memory import update_performance
            update_performance(ctx, fallback, success=False, was_fallback=True)
        except Exception:
            pass

        success = run_fn(ctx, session_type, session_num, agent_override=fallback)
        if success:
            print(f"  [Launcher] Fallback {agent_label} succeeded.")
            return True

        if fallback is None:
            break  # already tried generic, give up
        fallback = _get_fallback_agent(fallback, ctx)
        if fallback is None and original_agent is not None:
            # One more try with generic
            original_agent = None
            continue
        break

    print(f"  [Launcher] All retries exhausted for session #{session_num}.")
    return False


def launch_parallel(ctx: ProjectContext, session_num: int,
                    max_parallel: int = 2) -> list[dict]:
    """Launch parallel agent sessions using worktree isolation.

    Reads the task graph, finds independent tasks that can run in parallel,
    and spawns each in its own git worktree.

    Returns list of {"task": str, "agent": str, "success": bool}.
    """
    from task_graph import TaskGraph
    from worktree import create_worktree, merge_worktree, cleanup_worktree
    from run import run_session

    # Load backlog and find parallel batches
    backlog_file = ctx.memory_dir / "backlog.md"
    if not backlog_file.exists():
        print("  [Launcher] No backlog found.")
        return []

    text = backlog_file.read_text(encoding="utf-8")
    graph = TaskGraph.from_backlog(text)

    if graph.has_cycle():
        print("  [Launcher] WARNING: Task graph has cycles — running sequentially.")
        return []

    batches = graph.find_parallel_batches(max_batch_size=max_parallel)
    if not batches:
        print("  [Launcher] No ready tasks in backlog.")
        return []

    summary = graph.summary()
    print(f"  [Launcher] Task graph: {summary['remaining']} remaining, "
          f"{summary['ready_now']} ready, {summary['parallel_batches']} batches, "
          f"critical path: {summary['critical_path_length']} steps")

    # Execute first batch (independent tasks)
    batch = batches[0]
    results = []

    if len(batch) == 1:
        # Single task — no need for worktree isolation
        task = batch[0]
        print(f"  [Launcher] Single task: {task.name} (agent: {task.agent_hint or 'auto'})")
        success = launch_with_retry(ctx, "work", session_num)
        results.append({
            "task": task.name,
            "agent": task.agent_hint or "auto",
            "success": success,
        })
    else:
        # Multiple independent tasks — use worktrees
        print(f"  [Launcher] Parallel batch: {len(batch)} independent tasks")
        for i, task in enumerate(batch):
            agent = task.agent_hint
            sub_session = session_num + i
            print(f"    [{i+1}/{len(batch)}] {task.name} (agent: {agent or 'auto'})")

            # Create worktree for this agent
            ws = create_worktree(ctx.project_root, agent or "generic", sub_session)
            if not ws:
                print(f"    Failed to create worktree — running in main tree")
                success = run_session(ctx, "work", sub_session, agent_override=agent)
            else:
                # Run session in worktree
                success = run_session(ctx, "work", sub_session,
                                      agent_override=agent,
                                      worktree_dir=ws.worktree_dir)

                # Merge back and cleanup
                if success:
                    merged = merge_worktree(ws, ctx.project_root)
                    if not merged:
                        print(f"    WARNING: Merge failed for {task.name} — "
                              f"changes preserved on branch {ws.branch_name}")
                        success = False
                cleanup_worktree(ws, ctx.project_root, delete_branch=success)

            results.append({
                "task": task.name,
                "agent": agent or "auto",
                "success": success,
            })

    return results
