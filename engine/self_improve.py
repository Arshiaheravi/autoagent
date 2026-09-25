#!/usr/bin/env python3
"""Agency Self-Improvement System — orchestrator + CLI entry point.

Analysis functions live in self_improve_analyzers.py.
This file handles:
- Autonomous scheduling (cron-ready entry point)
- Post-session hook (runs all improvement layers)
- CLI entry point
"""
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Env loading + preflight canary ─────────────────────────────
# Cron-spawned processes inherit only PATH/PYTHONPATH from the LaunchAgent
# plist. All API keys live in ~/Documents/autoagent/.env (chmod 600,
# gitignored). load_dotenv runs before any council/SDK import so missing
# keys surface here, not 30 minutes into a session. Reason for the canary:
# 2026-04-14 incident silently lost ANTHROPIC_API_KEY via .zshenv edit and
# council degraded for days before anyone noticed.
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / "Documents" / "autoagent" / ".env")
except Exception as _dotenv_err:  # noqa: BLE001
    print(f"[autoagent] dotenv load failed: {_dotenv_err}", file=sys.stderr)

# Anthropic NOT in REQUIRED_KEYS — Claude is billed via Max plan through the
# `claude` CLI binary (auth lives in ~/.claude/credentials, not env). The
# CLI presence check below covers it.
REQUIRED_KEYS = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
)


def _preflight_keys() -> list[str]:
    return [k for k in REQUIRED_KEYS if not os.environ.get(k)]


def _preflight_cli() -> bool:
    import shutil
    return bool(shutil.which("claude"))


def _enforce_preflight() -> None:
    missing = _preflight_keys()
    cli_ok = _preflight_cli()
    failures: list[str] = []
    if missing:
        failures.append(f"missing API keys: {', '.join(missing)}")
    if not cli_ok:
        failures.append("claude CLI not found on PATH (Max-plan billing path broken)")
    if failures:
        msg = "[autoagent] PREFLIGHT FAIL — " + "; ".join(failures)
        print(msg, file=sys.stderr)
        log_path = Path.home() / "Library" / "Logs" / "autoagent-cron.err"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
        except Exception:
            pass
        sys.exit(1)


from registry import ProjectContext, AGENCY_HOME, list_projects, get

# ── Agency-wide PID lock ────────────────────────────────────────
AGENCY_LOCK = AGENCY_HOME / ".agency.lock"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _orphan_agency_pid() -> int:
    """Find any live agency process (self_improve.py, engine/run.py, engine/launcher.py)
    other than ourselves. Returns PID or 0."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "engine/(run\\.py|self_improve\\.py|launcher\\.py)"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != os.getpid() and _pid_alive(pid):
                return pid
    except Exception:
        pass
    return 0


def _acquire_agency_lock() -> bool:
    """Agency-wide PID mutex. Blocks concurrent cron/launchd runs from double-spending.
    Returns False if another agency process is active."""
    AGENCY_LOCK.parent.mkdir(parents=True, exist_ok=True)
    if AGENCY_LOCK.exists():
        try:
            existing = int(AGENCY_LOCK.read_text().strip())
        except (ValueError, OSError):
            existing = 0
        if existing and _pid_alive(existing):
            logger.warning("Agency lock held by PID %d — exiting", existing)
            print(f"  [Agency] Another run in progress (PID {existing}). Exiting.")
            return False
        logger.info("Stale lock from PID %d — overwriting", existing)
    orphan = _orphan_agency_pid()
    if orphan:
        print(f"  [Agency] Orphaned engine process alive (PID {orphan}). Exiting.")
        print(f"  [Agency] To recover: kill {orphan}  (then re-run)")
        return False
    AGENCY_LOCK.write_text(str(os.getpid()))
    return True


def _release_agency_lock():
    try:
        if AGENCY_LOCK.exists():
            owner = int(AGENCY_LOCK.read_text().strip() or 0)
            if owner == os.getpid():
                AGENCY_LOCK.unlink()
    except Exception:
        pass

# Backward-compatible re-exports — callers can still import from self_improve
from self_improve_analyzers import (  # noqa: F401
    share_knowledge_across_projects,
    share_security_findings_across_projects,
    inject_production_metrics,
    generate_skill_from_knowledge,
    quality_gate_check,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# AUTONOMOUS SCHEDULING ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def run_autonomous(project_names: Optional[list[str]] = None,
                   max_sessions: int = 10,
                   cooldown: int = 60) -> dict:
    """Run sessions autonomously — designed for cron/launchd/systemd.

    Returns summary of what was done.

    Usage in crontab (every 2 hours):
        0 */2 * * * cd ~/Documents/autoagent && python3 engine/self_improve.py auto

    Or with specific projects:
        python3 engine/self_improve.py auto myapp otherapp
    """
    from runner import run_project, generate_dashboard
    from session_helpers import get_session_type

    if not _acquire_agency_lock():
        return {"sessions": 0, "skipped": "lock_held"}
    import atexit
    atexit.register(_release_agency_lock)

    if project_names:
        contexts = [get(n) for n in project_names]
    else:
        contexts = [get(p["name"]) for p in list_projects()]

    results = {"sessions": 0, "projects": {}, "started": datetime.now(timezone.utc).isoformat()}

    for ctx in contexts:
        try:
            # Check if paused via Telegram /pause command
            try:
                from comms import is_paused
                if is_paused():
                    logger.info("Agency PAUSED — skipping %s", ctx.name)
                    results["projects"][ctx.name] = {"skipped": "paused"}
                    continue
            except Exception:
                pass

            session_num = 1
            if ctx.counter_file.exists():
                try:
                    session_num = json.loads(ctx.counter_file.read_text()).get("count", 1)
                except Exception:
                    pass

            stype = get_session_type(session_num)
            # Health override: if recent sessions are failing/no-op, force META next
            try:
                from session_analytics import health_auto_meta
                if stype == "work" and health_auto_meta(ctx.sessions_file):
                    logger.info("Health trigger: auto-META for %s (recent sessions unhealthy)", ctx.name)
                    print(f"  [Agency] Health trigger: auto-META for {ctx.name}")
                    stype = "meta"
            except Exception as e:
                logger.debug("health_auto_meta check skipped: %s", e)

            from launcher import launch_with_retry
            from run import run_session
            success = launch_with_retry(ctx, stype, session_num, run_fn=run_session)

            generate_dashboard(ctx)
            ctx.counter_file.write_text(json.dumps({"count": session_num + 1}))

            results["projects"][ctx.name] = {
                "session": session_num,
                "type": stype,
                "success": success,
            }
            results["sessions"] += 1

            if results["sessions"] >= max_sessions:
                break

            time.sleep(cooldown)
        except Exception as e:
            logger.error("Auto session failed for %s: %s", ctx.name, e)
            results["projects"][ctx.name] = {"error": str(e)}

    # Post-run: share knowledge and security findings across projects
    try:
        shared = share_knowledge_across_projects()
        results["knowledge_shared"] = shared
    except Exception:
        pass
    try:
        sec_shared = share_security_findings_across_projects()
        results["security_findings_shared"] = sec_shared
    except Exception:
        pass

    results["finished"] = datetime.now(timezone.utc).isoformat()
    return results


# ══════════════════════════════════════════════════════════════════
# POST-SESSION HOOK — Runs all improvement layers
# ══════════════════════════════════════════════════════════════════

def post_session_improve(ctx: ProjectContext) -> dict:
    """Run all self-improvement layers after a session completes.

    Call this from run.py after each session.
    """
    results = {}

    # Quality gate
    try:
        results["quality_gate"] = quality_gate_check(ctx)
    except Exception as e:
        results["quality_gate"] = {"error": str(e)}

    # Production metrics
    try:
        results["metrics"] = inject_production_metrics(ctx)
    except Exception as e:
        results["metrics"] = {"error": str(e)}

    # Skill generation (only on META sessions — don't slow work sessions)
    try:
        skill = generate_skill_from_knowledge(ctx)
        if skill:
            results["skill_generated"] = skill
    except Exception:
        pass

    # Visual regression check (only when frontend files changed)
    try:
        from visual_check import post_session_visual_check
        visual = post_session_visual_check(ctx)
        if visual:
            results["visual_check"] = {
                "ok": visual["ok"],
                "issues": visual.get("issues", []),
                "pages_checked": visual.get("pages_checked", 0),
            }
    except Exception:
        pass

    # Agent-as-Judge — external session verdict
    try:
        from judge import judge_session, write_verdict, infer_session_signals
        sessions_data = json.loads(ctx.sessions_file.read_text()) if ctx.sessions_file.exists() else []
        if sessions_data:
            last = sessions_data[-1]
            diff_result = subprocess.run(
                ["git", "-C", str(ctx.project_root), "diff", "HEAD~1", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            # Derive tests_passed (tri-state), exit_code, claimed_success from
            # the (schema-varying) session entry. Absence of a field is not a
            # failure signal — see infer_session_signals.
            sig = infer_session_signals(last)
            _judge_t0 = time.monotonic()
            verdict = judge_session(
                session_id=str(last.get("session", "?")),
                diff_text=diff_result.stdout[:8000],
                tests_passed=sig["tests_passed"],
                exit_code=sig["exit_code"],
                claimed_success=sig["claimed_success"],
                session_summary=last.get("summary", ""),
            )
            # Wall-clock of the whole judge (dominated by the rubric LLM call).
            # Recorded so nested-claude latency is visible in judge_verdicts.jsonl
            # without a manual stopwatch — decides whether the SDK judge is worth it.
            verdict["judge_elapsed_s"] = round(time.monotonic() - _judge_t0, 1)
            verdicts_file = ctx.memory_dir / "judge_verdicts.jsonl"
            write_verdict(verdict, verdicts_file)
            results["judge"] = {
                "verdict": verdict["verdict"],
                "disagreement": verdict["disagreement"],
                "elapsed_s": verdict["judge_elapsed_s"],
            }
    except Exception as e:
        logger.debug("judge check skipped: %s", e)

    return results


# ══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    args = sys.argv[1:]
    if not args or args[0] == "help":
        print("""
  AutoAgent Self-Improvement System

  Usage:
    python3 engine/self_improve.py auto [project1 project2 ...]
        Run 1 session per project autonomously (cron-safe)

    python3 engine/self_improve.py share
        Share knowledge across all projects

    python3 engine/self_improve.py metrics [project]
        Inject production metrics into project knowledge

    python3 engine/self_improve.py gate [project]
        Run quality gate check on latest session

    python3 engine/self_improve.py skills [project]
        Generate skills from knowledge patterns
""")
        sys.exit(0)

    import os
    os.chdir(Path(__file__).parent)
    cmd = args[0]

    if cmd == "auto":
        _enforce_preflight()
        project_names = args[1:] if len(args) > 1 else None
        result = run_autonomous(project_names)
        print(json.dumps(result, indent=2))

    elif cmd == "share":
        count = share_knowledge_across_projects()
        print(f"Shared {count} rules across projects.")

    elif cmd == "metrics":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        summary = inject_production_metrics(ctx)
        print(summary or "No metrics to inject.")

    elif cmd == "gate":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        result = quality_gate_check(ctx)
        print(json.dumps(result, indent=2))

    elif cmd == "skills":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        skill = generate_skill_from_knowledge(ctx)
        print(f"Generated skill: {skill}" if skill else "No skill patterns found.")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
