"""Tests for event_emitter.py — emit() and read_events()."""
import json
from pathlib import Path

from event_emitter import emit, read_events


def test_emit_writes_valid_jsonl(tmp_path):
    """emit() appends a valid JSON line with timestamp and kwargs."""
    f = tmp_path / "events.jsonl"
    emit(f, project="demo", type="tool_use", action="writing")
    lines = f.read_text().strip().split("\n")
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["project"] == "demo"
    assert event["type"] == "tool_use"
    assert event["action"] == "writing"
    assert "timestamp" in event


def test_read_events_empty_file(tmp_path):
    """read_events returns [] for a nonexistent file."""
    f = tmp_path / "events.jsonl"
    assert read_events(f) == []


def test_read_events_skips_malformed_json(tmp_path):
    """read_events silently skips lines that aren't valid JSON."""
    f = tmp_path / "events.jsonl"
    f.write_text('{"ok": 1}\nNOT_JSON\n{"ok": 2}\n')
    events = read_events(f)
    assert len(events) == 2
    assert events[0]["ok"] == 1
    assert events[1]["ok"] == 2


def test_read_events_last_n_limit(tmp_path):
    """read_events(last_n=N) returns only the last N events."""
    f = tmp_path / "events.jsonl"
    for i in range(10):
        emit(f, seq=i)
    events = read_events(f, last_n=3)
    assert len(events) == 3
    assert events[0]["seq"] == 7
    assert events[1]["seq"] == 8
    assert events[2]["seq"] == 9


# ── Tests moved from test_dashboard.py ──

def test_emit_event_writes_jsonl_with_fields(tmp_path):
    """emit() writes all keyword fields plus timestamp."""
    events_file = tmp_path / "events.jsonl"
    emit(events_file, project="test", session=1, type="tool_use",
         action="reading", target="src/app.py")
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["project"] == "test"
    assert ev["session"] == 1
    assert ev["type"] == "tool_use"
    assert ev["action"] == "reading"
    assert "timestamp" in ev


def test_emit_multiple_events_appends(tmp_path):
    """Multiple emit() calls append lines."""
    events_file = tmp_path / "events.jsonl"
    emit(events_file, project="test", session=1, type="session_start")
    emit(events_file, project="test", session=1, type="tool_use", action="writing", target="x.py")
    emit(events_file, project="test", session=1, type="session_end")
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 3


def test_emit_creates_file_if_missing(tmp_path):
    """emit() creates the file when it doesn't exist yet."""
    events_file = tmp_path / "subdir" / "events.jsonl"
    events_file.parent.mkdir(parents=True)
    emit(events_file, project="test", session=1, type="test")
    assert events_file.exists()
