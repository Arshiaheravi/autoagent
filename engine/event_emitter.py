#!/usr/bin/env python3
"""Event emitter — writes structured events to JSONL for the live dashboard."""
import json
from datetime import datetime, timezone
from pathlib import Path


def emit(events_file: Path, **kwargs):
    """Append a structured event to the JSONL file.

    Usage:
        emit(path, project="myapp", session=7, type="tool_use",
             action="writing", target="src/app.py")
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def read_events(events_file: Path, last_n: int = 50) -> list[dict]:
    """Read the last N events from the JSONL file."""
    if not events_file.exists():
        return []
    lines = events_file.read_text(encoding="utf-8").strip().split("\n")
    events = []
    for line in lines[-last_n:]:
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events
