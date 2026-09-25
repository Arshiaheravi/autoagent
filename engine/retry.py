"""Exponential backoff for Claude CLI rate-limit errors.

Pure function: should_retry() takes exit code, attempt number, and error text,
returns (should_retry: bool, wait_seconds: int).

I/O helpers: save_last_error / read_last_error persist error context between
run_session() and launch_with_retry() via a small temp file.
"""
from pathlib import Path

from model_fallback import is_rate_limit_error

# Backoff schedule: attempt 0 → 30s, 1 → 60s, 2 → 120s
_BACKOFF_SECONDS = [30, 60, 120]
_MAX_ATTEMPTS = len(_BACKOFF_SECONDS)

def should_retry(exit_code: int, attempt: int, last_error: str) -> tuple[bool, int]:
    """Decide whether to retry a failed Claude CLI invocation.

    Args:
        exit_code: Process exit code (0 = success).
        attempt: Zero-based attempt number (0 = first try).
        last_error: Stderr/error message from the failed process.

    Returns:
        (do_retry, wait_seconds). If do_retry is False, wait_seconds is 0.
    """
    # Success — no retry needed
    if exit_code == 0:
        return False, 0

    # Exceeded max attempts
    if attempt >= _MAX_ATTEMPTS:
        return False, 0

    # Only retry on rate-limit / capacity errors
    if not last_error or not is_rate_limit_error(last_error):
        return False, 0

    return True, _BACKOFF_SECONDS[attempt]


_ERROR_FILE = "_last_session_error.txt"
_MAX_ERROR_CHARS = 2000


def save_last_error(memory_dir: Path, error_lines: list[str]) -> None:
    """Save last error context for the launcher to read."""
    text = "\n".join(error_lines[-20:])[-_MAX_ERROR_CHARS:]
    (memory_dir / _ERROR_FILE).write_text(text, encoding="utf-8")


def read_last_error(memory_dir: Path) -> str:
    """Read saved error context. Returns empty string if none."""
    f = memory_dir / _ERROR_FILE
    if f.exists():
        return f.read_text(encoding="utf-8")
    return ""
