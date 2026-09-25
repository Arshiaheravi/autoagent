"""JIT context utilities — load on demand, truncate responses, compact context."""

import re
import subprocess
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token for English text."""
    return len(text) // 4


def truncate_response(text: str, max_chars: int = 2000) -> str:
    """Truncate text at sentence boundary, append [truncated] marker."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_period = cut.rfind(".")
    if last_period > max_chars // 2:
        cut = cut[: last_period + 1]
    else:
        last_space = cut.rfind(" ")
        if last_space > 0:
            cut = cut[:last_space]
    return cut + " [truncated]"


def compact_context(text: str, max_chars: int = 8000) -> str:
    """Remove raw tool output blocks, keep decision lines and normal context."""
    cleaned = re.sub(
        r"---\s*RAW TOOL OUTPUT\s*---.*?---\s*END TOOL OUTPUT\s*---\s*\n?",
        "",
        text,
        flags=re.DOTALL,
    )
    if len(cleaned) <= max_chars:
        return cleaned
    return truncate_response(cleaned, max_chars)


def load_jit(ref: str, search_root: Path | None = None) -> str:
    """Load context on demand from a file path or search query.

    If ref is an existing file path, read and return its content.
    If search_root is provided, grep for ref in that directory.
    """
    path = Path(ref)
    if path.exists() and path.is_file():
        try:
            return path.read_text(errors="replace")[:8000]
        except OSError:
            return ""

    if search_root is None:
        return ""

    search_root = Path(search_root)
    if not search_root.is_dir():
        return ""

    try:
        result = subprocess.run(
            ["grep", "-r", "-l", "--include=*.py", "--include=*.md",
             ref, str(search_root)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""

        matches = result.stdout.strip().splitlines()[:3]
        parts = []
        for match_path in matches:
            try:
                content = Path(match_path).read_text(errors="replace")
                parts.append(f"--- {match_path} ---\n{content[:2000]}")
            except OSError:
                continue
        return "\n\n".join(parts)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
