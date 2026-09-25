"""Cross-session failure pattern detector.

Parses activity_log.md for FAILED/BLOCKED entries, clusters by error type,
and returns sorted list of recurring failure signatures.
"""
from __future__ import annotations

import re
from collections import defaultdict


_SECTION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b.*", re.MULTILINE)
_FAILURE_RE = re.compile(
    r"^(?:FAILED|BLOCKED):\s*(\w+(?:Error|Exception|Warning)?)\b(.*)$",
    re.MULTILINE,
)


def detect_failure_patterns(log_text: str) -> list[dict]:
    """Parse activity log text and cluster failures by error type.

    Returns list of dicts sorted by count descending:
        [{"error_type": str, "count": int, "sessions": [str], "examples": [str]}]
    """
    if not log_text or not log_text.strip():
        return []

    sections = _SECTION_RE.split(log_text)
    # sections alternates: [preamble, date1, body1, date2, body2, ...]

    clusters: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "sessions": [], "examples": []}
    )

    for i in range(1, len(sections) - 1, 2):
        date = sections[i]
        body = sections[i + 1]

        for match in _FAILURE_RE.finditer(body):
            error_type = match.group(1)
            detail = match.group(2).strip().rstrip(".")
            entry = clusters[error_type]
            entry["count"] += 1
            if date not in entry["sessions"]:
                entry["sessions"].append(date)
            if detail and len(entry["examples"]) < 3:
                entry["examples"].append(detail)

    if not clusters:
        # Fallback: look for FAILED/BLOCKED lines without typed errors
        fallback_re = re.compile(
            r"^(?:FAILED|BLOCKED):\s*(.+)$", re.MULTILINE
        )
        for i in range(1, len(sections) - 1, 2):
            date = sections[i]
            body = sections[i + 1]
            for match in fallback_re.finditer(body):
                line = match.group(1).strip()
                word = line.split()[0] if line.split() else "Unknown"
                entry = clusters[word]
                entry["count"] += 1
                if date not in entry["sessions"]:
                    entry["sessions"].append(date)
                if len(entry["examples"]) < 3:
                    entry["examples"].append(line[:120])

    result = [
        {
            "error_type": etype,
            "count": data["count"],
            "sessions": data["sessions"],
            "examples": data["examples"],
        }
        for etype, data in clusters.items()
    ]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result
