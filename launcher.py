#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoAgent Launcher — Self-healing wrapper for run.py

Instead of running run.py directly, run this:
    py -X utf8 autoagent/launcher.py --tasks 2

What it does:
  - Starts run.py normally
  - If run.py crashes for ANY reason (SyntaxError, NameError, any bug),
    it automatically asks Claude to fix run.py, then restarts
  - Repeats until run.py finishes cleanly or max retries reached
  - You never need to manually fix bugs — it fixes itself
"""
import io
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT       = Path(__file__).resolve().parent.parent
AGENT_DIR  = Path(__file__).resolve().parent
RUN_PY     = AGENT_DIR / "run.py"
HEAL_LOG   = AGENT_DIR / "self_heal_log.md"
LOCK_FILE  = AGENT_DIR / ".autoagent.lock"
CONFIG_FILE = AGENT_DIR / "config.json"
HEALER_WEEKLY_FILE = AGENT_DIR / "healer_weekly.json"
MAX_RETRIES = 2   # max auto-fix attempts before giving up (halved post 2026-04-16 audit)


def _load_cfg() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _iso_week_key() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _healer_budget() -> tuple[float, float, float]:
    """Return (weekly_spent, weekly_cap, per_attempt_estimate) — in USD."""
    cfg = _load_cfg()
    cap = float(cfg.get("healer_weekly_usd", 75.0))
    est = float(cfg.get("healer_attempt_estimate_usd", 1.50))
    spent = 0.0
    if HEALER_WEEKLY_FILE.exists():
        try:
            data = json.loads(HEALER_WEEKLY_FILE.read_text(encoding="utf-8"))
            spent = float(data.get(_iso_week_key(), 0.0))
        except Exception:
            pass
    return spent, cap, est


def _healer_budget_ok() -> tuple[bool, str]:
    spent, cap, est = _healer_budget()
    if spent + est > cap:
        return False, f"healer weekly budget ${spent:.2f} + ${est:.2f} est > ${cap:.2f} cap"
    return True, f"healer weekly spent ${spent:.2f} / ${cap:.2f}"


def _healer_log_attempt():
    """Record an estimated-cost heal attempt against the current ISO week."""
    _, _, est = _healer_budget()
    data = {}
    if HEALER_WEEKLY_FILE.exists():
        try:
            data = json.loads(HEALER_WEEKLY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    key = _iso_week_key()
    data[key] = round(float(data.get(key, 0.0)) + est, 2)
    HEALER_WEEKLY_FILE.write_text(json.dumps(data, indent=2))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _orphan_run_py_pid() -> int:
    """Return PID of a live run.py with no parent launcher, else 0.

    Orphans arise when a prior launcher exited (or was killed) but left its
    spawned run.py alive — those keep spending budget outside the PID lock.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", "autoagent/run\\.py"],
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


def _acquire_lock() -> bool:
    """Create PID lock. Returns False if another launcher OR orphaned run.py is active."""
    if LOCK_FILE.exists():
        try:
            existing = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            existing = 0
        if existing and _pid_alive(existing):
            print(f"  [Launcher] Another autoagent instance is running (PID {existing}). Exiting.")
            return False
        print(f"  [Launcher] Stale lock from PID {existing} — overwriting.")
    orphan = _orphan_run_py_pid()
    if orphan:
        print(f"  [Launcher] Orphaned run.py still alive (PID {orphan}). Exiting to prevent concurrent burn.")
        print(f"  [Launcher] To recover: kill {orphan}  (then re-run)")
        return False
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    try:
        if LOCK_FILE.exists():
            owner = int(LOCK_FILE.read_text().strip() or 0)
            if owner == os.getpid():
                LOCK_FILE.unlink()
    except Exception:
        pass

def _find_claude() -> str:
    import shutil
    found = shutil.which("claude")
    if found:
        return found
    if sys.platform == "win32":
        npm_bin = os.path.join(os.environ.get("APPDATA", ""), "npm")
        win_path = os.path.join(npm_bin, "claude.cmd")
        if os.path.exists(win_path):
            return win_path
    return "claude"

CLAUDE_CMD = _find_claude()


def _claude_available() -> bool:
    import shutil
    return shutil.which(CLAUDE_CMD) is not None or os.path.exists(CLAUDE_CMD)


def _ask_claude_to_fix(error_output: str, attempt: int):
    """Call Claude CLI to fix run.py given the error output."""
    if not _claude_available():
        print("  [Launcher] Claude CLI not found — cannot auto-fix.")
        return False

    ok, status = _healer_budget_ok()
    if not ok:
        print(f"  [Launcher] {status} — skipping heal. Raise healer_weekly_usd in config.json to continue.")
        return False
    print(f"  [Launcher] {status}")
    _healer_log_attempt()

    heal_prompt = f"""You are fixing a bug in an autonomous AI agent file: run.py

ERROR THAT CAUSED THE CRASH:
{error_output[:3000]}

YOUR TASK (do all steps):
1. Read the file run.py (repo root)
2. Find the exact cause of this error
3. Fix it with the minimal change needed — do NOT refactor anything else
4. Verify syntax: py -X utf8 -c "import ast; ast.parse(open('run.py', encoding='utf-8').read()); print('syntax ok')"
5. If syntax ok, commit the fix:
   git add run.py && git commit -m "self-heal attempt {attempt}: fix {error_output[:80].strip()}" && git push

RULES:
- Fix ONLY what caused the crash — nothing else
- If you cannot find the root cause, wrap the failing section in try/except so it logs and continues instead of crashing
- The file must be valid Python after your fix
- End your response with either FIXED or COULD_NOT_FIX
- Ambiguous output (no FIXED token) is treated as failure — retry budget will not be spent on partial fixes
"""
    import tempfile
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(heal_prompt)
            tmp = f.name
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        if sys.platform == "win32":
            cmd = f'type "{tmp}" | "{CLAUDE_CMD}" --print --dangerously-skip-permissions --max-turns 30'
        else:
            cmd = f'cat "{tmp}" | "{CLAUDE_CMD}" --print --dangerously-skip-permissions --max-turns 30'
        print(f"  [Launcher] Asking Claude to fix the bug (attempt {attempt}/{MAX_RETRIES})...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=600,
                                env=env, cwd=str(ROOT))
        output = result.stdout.strip()
        # Require explicit FIXED token; any other output (including silence or
        # an apology) is treated as failure. Prior "assume fixed if any output"
        # behavior let unfixable bugs burn the retry budget.
        if "FIXED" in output and "COULD_NOT_FIX" not in output:
            print(f"  [Launcher] Fix applied successfully.")
            return True
        if "COULD_NOT_FIX" in output:
            print(f"  [Launcher] Claude could not fix this error.")
            return False
        print(f"  [Launcher] Ambiguous output — no FIXED token. Treating as failure.")
        return False
    except Exception as e:
        print(f"  [Launcher] Heal attempt failed: {e}")
        return False
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass


def _log_heal(error_output: str, attempt: int, fixed: bool):
    from datetime import datetime
    entry = (
        f"\n---\n"
        f"## {datetime.now().strftime('%Y-%m-%d %H:%M')} — Attempt {attempt} — {'FIXED' if fixed else 'FAILED'}\n"
        f"```\n{error_output[:1000]}\n```\n"
    )
    with open(HEAL_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def _syntax_check() -> tuple[bool, str]:
    """Check if run.py has valid syntax. Returns (ok, error_message)."""
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             f"import ast; ast.parse(open(r'{RUN_PY}', encoding='utf-8').read()); print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        if "ok" in result.stdout:
            return True, ""
        return False, result.stderr or result.stdout
    except Exception as e:
        return False, str(e)


def run():
    args = sys.argv[1:]  # pass all args through to run.py (e.g. --tasks 2)
    attempt = 0

    read_only = any(a in args for a in ("--status", "--test"))
    if not read_only:
        if not _acquire_lock():
            sys.exit(2)
    import atexit
    atexit.register(_release_lock)

    while attempt <= MAX_RETRIES:
        # Syntax check before launching
        ok, syntax_err = _syntax_check()
        if not ok:
            attempt += 1
            print(f"\n  [Launcher] SyntaxError in run.py before launch:")
            print(f"  {syntax_err.strip()}")
            fixed = _ask_claude_to_fix(f"SyntaxError before launch:\n{syntax_err}", attempt)
            _log_heal(syntax_err, attempt, fixed)
            if not fixed:
                print(f"  [Launcher] Could not fix syntax error. Manual intervention needed.")
                sys.exit(1)
            time.sleep(2)
            continue  # retry after fix

        # Launch run.py
        cmd = [sys.executable, "-X", "utf8", str(RUN_PY)] + args
        print(f"\n  [Launcher] Starting run.py (attempt {attempt + 1})...")
        try:
            result = subprocess.run(cmd, cwd=str(ROOT))
            if result.returncode == 0:
                print(f"\n  [Launcher] run.py completed successfully.")
                return  # clean exit
            else:
                # Non-zero exit — something went wrong
                error_msg = f"run.py exited with code {result.returncode}"
                print(f"\n  [Launcher] {error_msg}")
                attempt += 1
                if attempt > MAX_RETRIES:
                    break
                fixed = _ask_claude_to_fix(error_msg, attempt)
                _log_heal(error_msg, attempt, fixed)
                if not fixed:
                    print(f"  [Launcher] Could not fix. Retrying anyway...")
                time.sleep(3)

        except KeyboardInterrupt:
            print("\n  [Launcher] Stopped by user.")
            return
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            print(f"\n  [Launcher] Unexpected crash: {error_msg}")
            attempt += 1
            if attempt > MAX_RETRIES:
                break
            fixed = _ask_claude_to_fix(error_msg, attempt)
            _log_heal(error_msg, attempt, fixed)
            time.sleep(3)

    print(f"\n  [Launcher] Max retries ({MAX_RETRIES}) reached. Please check self_heal_log.md")
    sys.exit(1)


if __name__ == "__main__":
    run()
