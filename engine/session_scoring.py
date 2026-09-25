"""Session scoring, labels, and health heuristics — pure functions."""
import json
from pathlib import Path


def format_session_label(session_num: int, agent: str = "", task: str = "",
                         files_count: int = 0, test_count: int = 0, success: bool = True) -> str:
    """Build a rich one-liner: #192 [frontend] "Fix mobile overflow" — 3 files, 12 tests, OK"""
    parts = [f"#{session_num}"]
    if agent: parts.append(f"[{agent}]")
    t = (task[:60] + "…") if len(task) > 60 else task
    if t: parts.append(f'"{t}"')
    meta = []
    if files_count: meta.append(f"{files_count} files")
    if test_count: meta.append(f"{test_count} tests")
    meta.append("OK" if success else "FAIL")
    parts.append("— " + ", ".join(meta))
    return " ".join(parts)


def compute_quality_score(
    tasks_completed: int, tests_added: int, tests_broken: int, retries: int
) -> int:
    """Compute a 0-100 quality score for a session."""
    task_pts = 40 if tasks_completed >= 1 else 0
    test_pts = min(tests_added * 12, 60)
    penalty = tests_broken * 20 + retries * 5
    return max(0, min(100, task_pts + test_pts - penalty))


def compute_task_impact_score(
    tests_added: int, quality_delta: int,
    commit_produced: bool, regressions: int,
) -> int:
    """Score a completed task 0-10: tests(0-3) + quality(0-3) + commit(0-2) + no_regressions(0-2)."""
    t = 3 if tests_added >= 5 else 2 if tests_added >= 3 else 1 if tests_added >= 1 else 0
    q = 3 if quality_delta >= 25 else 2 if quality_delta >= 10 else 1 if quality_delta >= 1 else 0
    return min(t + q + (2 if commit_produced else 0) + (2 if regressions == 0 else 0), 10)


def _session_is_noop(entry: dict) -> bool:
    """A session is a 'no-op' if it produced no work or tests failed."""
    if not entry.get("files"):
        return True
    tests = entry.get("tests") or {}
    if tests.get("status") in ("fail", "error"):
        return True
    return False


def health_auto_meta(sessions_file) -> bool:
    """Return True if health heuristics say the NEXT session should be META.

    Triggers:
      - 3 consecutive no-op sessions in the most recent history, OR
      - No-op rate > 20% (>=4 of 15) in the last 15 sessions.
    """
    sessions_file = Path(sessions_file)
    if not sessions_file.exists():
        return False
    try:
        data = json.loads(sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, list) or len(data) < 3:
        return False
    if all(_session_is_noop(s) for s in data[-3:]):
        return True
    last_15 = data[-15:]
    if len(last_15) >= 15:
        noops = sum(1 for s in last_15 if _session_is_noop(s))
        if noops / 15 > 0.20:
            return True
    return False
