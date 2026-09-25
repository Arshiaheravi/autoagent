#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoAgent Agency — Session Runners & Status Display

Higher-level orchestration: run_project (single project loop),
run_continuous (multi-project round-robin), show_status, ask_mode,
generate_dashboard.  Core single-session logic stays in run.py.
"""
import json, os, time
from datetime import date, datetime, timedelta
from pathlib import Path

from registry import ProjectContext
from models import DEFAULT_DAILY_LIMIT_USD
from session_helpers import (
    get_session_type, build_prompt, parse_session_analytics,
    lifetime_cost_summary, weekly_cost_summary,
)

# Import engine/run.py explicitly — V1 root-level run.py shadows it
import importlib.util as _ilu
_run_spec = _ilu.spec_from_file_location("engine_run", Path(__file__).parent / "run.py")
_run_mod = _ilu.module_from_spec(_run_spec)
_run_spec.loader.exec_module(_run_mod)

budget_ok = _run_mod.budget_ok
run_session = _run_mod.run_session
log_cost = _run_mod.log_cost
weekly_session_ok = _run_mod.weekly_session_ok
log_session = _run_mod.log_session
CLAUDE = _run_mod.CLAUDE

# V1 launcher.py at repo root shadows engine/launcher.py — use importlib
_launcher_spec = _ilu.spec_from_file_location("launcher_v2", Path(__file__).parent / "launcher.py")
_launcher_mod = _ilu.module_from_spec(_launcher_spec)
_launcher_spec.loader.exec_module(_launcher_mod)
launch_with_retry = _launcher_mod.launch_with_retry


# ── Branch guard ───────────────────────────────────────────────
def _assert_branch(ctx) -> bool:
    """Refuse to run if the project repo isn't on its configured git_branch.
    Stops the agent committing to the wrong branch (e.g. canonical memory-layer).
    No-op if the project has no git_branch configured."""
    import subprocess
    want = ctx.config.get("git_branch")
    if not want:
        return True
    try:
        cur = subprocess.run(
            ["git", "-C", str(ctx.project_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception as e:
        print(f"  [AutoAgent] branch check failed for {ctx.name}: {e}")
        return False
    if cur != want:
        print(f"  [AutoAgent] REFUSING {ctx.name}: repo on '{cur}', expected '{want}'.\n"
              f"             Run: git -C {ctx.project_root} checkout {want}")
        return False
    return True


# ── Dashboard ──────────────────────────────────────────────────
def generate_dashboard(ctx: ProjectContext):
    template_file = ctx.agency_home / "templates" / "dashboard.template.html"
    if not ctx.sessions_file.exists() or not template_file.exists():
        # Try V1 template location
        template_file = Path(__file__).parent.parent / "dashboard.template.html"
        if not template_file.exists():
            return
    try:
        sessions_data = ctx.sessions_file.read_text(encoding="utf-8")
        template = template_file.read_text(encoding="utf-8")
        ctx.dashboard_file.write_text(
            template.replace("__SESSIONS_DATA__", sessions_data), encoding="utf-8"
        )
        print(f"  [AutoAgent] Dashboard updated → {ctx.dashboard_file}")
    except Exception as e:
        print(f"  [AutoAgent] Dashboard update failed: {e}")


# ── Status ─────────────────────────────────────────────────────
def show_status(ctx: ProjectContext):
    today = str(date.today())
    spent = 0.0
    if ctx.budget_file.exists():
        try: spent = json.loads(ctx.budget_file.read_text()).get(today, 0.0)
        except Exception: pass
    limit = ctx.config.get("daily_limit_usd", DEFAULT_DAILY_LIMIT_USD)

    # Session analytics from sessions.json
    analytics = parse_session_analytics(ctx.sessions_file)

    lifetime = lifetime_cost_summary(ctx.budget_file)
    weekly = weekly_cost_summary(ctx.budget_file)

    print(f"\n  ┌─── {ctx.name} ───")
    print(f"  │ Budget today: ${spent:.4f} / ${limit:.2f}")
    print(f"  │ Last 7 days: ${weekly:.4f}  │  Lifetime: ${lifetime:.4f}")
    print(f"  │ Sessions: {analytics['total_sessions']}  │  Tests: {analytics['test_count_latest']} (+{analytics['tests_added']} added)")
    if analytics["avg_quality"]:
        print(f"  │ Avg quality: {analytics['avg_quality']}/100")
    if analytics["type_counts"]:
        breakdown = "  │  ".join(f"{t}: {c}" for t, c in sorted(analytics["type_counts"].items()))
        print(f"  │ Types:  {breakdown}")
    if analytics["recent"]:
        print(f"  │")
        print(f"  │ Recent sessions:")
        for s in analytics["recent"]:
            print(f"  │   #{s['session']} [{s['type']}] {s['summary'][:70]}")
    print(f"  └───")


# ── Mode selection ─────────────────────────────────────────────
def ask_mode() -> str:
    # Non-interactive launch (piped/detached stdin, cron, nohup): never block on
    # input(). A non-EOF pipe makes input() hang forever — this once stranded an
    # agency session for ~1h stuck on the mode prompt in total silence. Default to
    # CLI immediately when there's no TTY.
    import sys
    if not sys.stdin.isatty():
        return "cli"
    print("\n  ┌─────────────────────────────────────┐")
    print("  │       AutoAgent Agency — Mode        │")
    print("  ├─────────────────────────────────────┤")
    print("  │  1  CLI  (free, recommended)        │")
    print("  │  2  API  (paid, debug-friendly)     │")
    print("  └─────────────────────────────────────┘")
    while True:
        try:
            choice = input("  Choose [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "cli"
        if choice == "1": return "cli"
        if choice == "2": return "api"
        print("  Please enter 1 or 2.")


# ── Continuous runner (multi-project round-robin) ─────────────
def run_continuous(contexts: list[ProjectContext], cooldown: int = 60,
                   until: str | None = None, forced_type: str | None = None):
    """Run sessions in a round-robin loop across multiple projects."""
    if not contexts:
        print("  [AutoAgent] No projects to run.")
        return

    def _past_cutoff() -> bool:
        if not until:
            return False
        try:
            hh, mm = until.split(":")
            cutoff = datetime.now().replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            # If cutoff is in the past, it means tomorrow (e.g. --until 07:00 at 23:00)
            if cutoff <= datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=5):
                cutoff += timedelta(days=1)
            return datetime.now() >= cutoff
        except Exception:
            return False

    # Load counters for each project
    counters = {}
    for ctx in contexts:
        n = 1
        if ctx.counter_file.exists():
            try: n = json.loads(ctx.counter_file.read_text()).get("count", 1)
            except Exception: pass
        counters[ctx.name] = n

    max_iterations = int(os.getenv("MAX_CONTINUOUS_ITERATIONS", "200"))
    idx = 0
    iterations = 0
    try:
        while True:
            if iterations >= max_iterations:
                print(f"\n  [AutoAgent] Reached MAX_CONTINUOUS_ITERATIONS={max_iterations}. Stopping.")
                break
            if _past_cutoff():
                print(f"\n  [AutoAgent] Reached --until {until}. Stopping.")
                break

            ctx = contexts[idx % len(contexts)]
            session_num = counters[ctx.name]

            if not _assert_branch(ctx):
                idx += 1
                time.sleep(cooldown)
                continue

            if not budget_ok(ctx):
                print(f"  [AutoAgent] Budget hit for {ctx.name}, skipping.")
                idx += 1
                iterations += 1  # count skips so an all-over-budget loop stays bounded
                time.sleep(cooldown)  # avoid a tight CPU spin
                continue

            if not weekly_session_ok(ctx):
                print(f"  [AutoAgent] Weekly session budget reached for {ctx.name}, skipping.")
                idx += 1
                iterations += 1
                time.sleep(cooldown)
                continue

            stype = forced_type if forced_type else get_session_type(session_num)
            launch_with_retry(ctx, stype, session_num, run_fn=run_session)
            log_session(ctx)
            generate_dashboard(ctx)

            counters[ctx.name] = session_num + 1
            ctx.counter_file.write_text(json.dumps({"count": session_num + 1}))

            iterations += 1
            idx += 1
            time.sleep(cooldown)
    except KeyboardInterrupt:
        print(f"\n  [AutoAgent] Continuous runner stopped.")


# ── Main loop (for one project) ───────────────────────────────
def run_project(ctx: ProjectContext, tasks_limit=None, forced_type=None, test_mode=False):
    """Run the session loop for a single project."""
    import os, shutil

    if test_mode:
        print(f"\n  [AutoAgent] DRY RUN for {ctx.name}...")
        prompt = build_prompt(ctx, "work")
        print(f"  Prompt length : {len(prompt)} chars (~{len(prompt) // 4} tokens)")
        print(f"  Session type  : WORK")
        print(f"  Skills found  : {', '.join(p.name for p in ctx.all_skills())}")
        mem_files = list(ctx.memory_dir.glob("*.md"))
        print(f"  Memory files  : {', '.join(p.name for p in mem_files)}")
        print(f"  Claude CLI    : {'FOUND at ' + CLAUDE if shutil.which(CLAUDE) or os.path.exists(CLAUDE) else 'NOT FOUND'}")
        print(f"  Project root  : {ctx.project_root}")
        print(f"\n  Everything looks good. Run without --test to start.\n")
        return

    if not _assert_branch(ctx):
        return

    # Load session counter
    session_num = 1
    if ctx.counter_file.exists():
        try: session_num = json.loads(ctx.counter_file.read_text()).get("count", 1)
        except Exception: pass

    work_done = 0
    sessions_run = 0
    # Absolute session ceiling: a bounded run must never spawn unlimited sessions
    # when work sessions fail or non-work (meta/brain/audit) sessions interleave.
    # This is the burn guard — in CLI/Max mode it's the real cap (daily $ budget
    # does not apply there). 3x the requested work, or an env-overridable default.
    session_cap = tasks_limit * 3 if tasks_limit else int(os.getenv("MAX_PROJECT_SESSIONS", "200"))

    while True:
        if tasks_limit and work_done >= tasks_limit:
            print(f"\n  [AutoAgent] Done. {work_done} sessions completed for {ctx.name}.")
            break

        if sessions_run >= session_cap:
            print(f"\n  [AutoAgent] Session ceiling {session_cap} reached for {ctx.name} "
                  f"({work_done} work done). Stopping to prevent runaway spend.")
            break

        if not budget_ok(ctx):
            print(f"\n  [AutoAgent] Daily budget hit for {ctx.name}. Stopping.")
            break

        if not weekly_session_ok(ctx):
            print(f"\n  [AutoAgent] Weekly session budget reached for {ctx.name}. "
                  f"Stopping to preserve Claude quota for the rest of the week.")
            break

        stype = forced_type if forced_type else get_session_type(session_num)
        success = launch_with_retry(ctx, stype, session_num, run_fn=run_session)
        sessions_run += 1
        log_session(ctx)

        if stype == "work" and success:
            work_done += 1

        generate_dashboard(ctx)

        # Save counter
        ctx.counter_file.write_text(json.dumps({"count": session_num + 1}))
        session_num += 1

        if tasks_limit and work_done >= tasks_limit:
            print(f"\n  [AutoAgent] Done. {work_done} sessions completed for {ctx.name}.")
            break

        try:
            if tasks_limit:
                pass  # back-to-back
            else:
                print(f"\n  [AutoAgent] Sleeping 1min until next session...")
                time.sleep(60)
        except KeyboardInterrupt:
            print(f"\n  [AutoAgent] Stopped.")
            break
