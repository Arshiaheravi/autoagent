#!/usr/bin/env python3
"""Auto-refresh hook for activity_log.md — appends dated entry after each session."""
from datetime import datetime
from pathlib import Path


def append_activity_log_entry(log_path: Path, *, session_type: str,
                              summary: str, files: list[str]) -> str:
    """Format and prepend a dated activity log entry. Returns formatted entry."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    type_label = session_type.upper() if session_type else "WORK"
    files_str = ", ".join(files) if files else "(none)"

    entry = (
        f"\n## {date_str} — {type_label}\n"
        f"DONE: {summary}\n"
        f"IMPACT: Auto-logged by infrastructure\n"
        f"FILES: {files_str}\n"
    )

    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
    else:
        existing = "# activity log\n"

    header_end = existing.find("\n", existing.find("# activity log"))
    if header_end == -1:
        header_end = len(existing)

    updated = existing[:header_end] + "\n" + entry + existing[header_end:]
    log_path.write_text(updated, encoding="utf-8")
    return entry.strip()
