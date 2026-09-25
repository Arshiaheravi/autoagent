"""Tests for memory eviction — keep context relevant."""
import datetime
import textwrap
from pathlib import Path

import pytest

# memory.py lives alongside this test file
import importlib.util
_spec = importlib.util.spec_from_file_location("memory", Path(__file__).parent / "memory.py")
memory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(memory)


def _write(path: Path, text: str):
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


# ── test_evict_old_entries ──────────────────────────────────────────────
def test_evict_old_entries(tmp_path):
    """knowledge.md entries older than 30 days are archived to knowledge_archive.md."""
    old_date = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
    recent_date = datetime.date.today().isoformat()

    knowledge = tmp_path / "knowledge.md"
    _write(knowledge, f"""\
        # knowledge

        RULE: [{old_date}] Old rule that should be archived

        ### Session #1 Reflexion — {old_date}
        - ACCOMPLISHED: something old
        - FAILED: nothing
        - RULE: [{old_date}] old reflexion rule

        RULE: [{recent_date}] Recent rule that should stay

        ### Session #10 Reflexion — {recent_date}
        - ACCOMPLISHED: something recent
        - FAILED: nothing
        - RULE: [{recent_date}] recent reflexion rule
    """)

    archive = tmp_path / "knowledge_archive.md"
    memory.evict_old_entries(knowledge, archive, max_age_days=30)

    kept = knowledge.read_text(encoding="utf-8")
    archived = archive.read_text(encoding="utf-8")

    # Recent content stays
    assert f"RULE: [{recent_date}]" in kept
    assert "Session #10" in kept

    # Old content is archived
    assert f"RULE: [{old_date}] Old rule" in archived
    assert "Session #1" in archived

    # Old content removed from knowledge
    assert f"RULE: [{old_date}] Old rule" not in kept
    assert "Session #1 Reflexion" not in kept


# ── test_activity_log_sliding_window ────────────────────────────────────
def test_activity_log_sliding_window(tmp_path):
    """activity_log.md keeps last 30 entries, archives rest."""
    activity = tmp_path / "activity_log.md"
    archive = tmp_path / "activity_log_archive.md"

    # Build 35 entries (newest first, like real activity_log.md)
    lines = ["# activity log\n"]
    for i in range(35, 0, -1):
        lines.append(f"\n## 2026-01-{i:02d} 10:00 — FEATURE\n")
        lines.append(f"DONE: Task {i}\n")
        lines.append(f"IMPACT: Impact {i}\n")
        lines.append(f"FILES: file{i}.py\n")
    activity.write_text("".join(lines), encoding="utf-8")

    memory.sliding_window_activity_log(activity, archive, max_entries=30)

    kept = activity.read_text(encoding="utf-8")
    archived = archive.read_text(encoding="utf-8")

    # Should keep the 30 most recent (entries 6..35)
    assert "Task 35" in kept
    assert "Task 6" in kept
    assert "Task 5" not in kept

    # Oldest 5 should be archived
    assert "Task 1" in archived
    assert "Task 5" in archived
    assert "Task 6" not in archived


# ── test_archive_is_searchable ──────────────────────────────────────────
def test_archive_is_searchable(tmp_path):
    """Archived entries are still findable via grep (plain text, not deleted)."""
    archive = tmp_path / "knowledge_archive.md"
    archive.write_text("RULE: [2025-01-01] Always use TDD\n", encoding="utf-8")

    # Simulate evicting more content into the same archive
    old_date = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    knowledge = tmp_path / "knowledge.md"
    _write(knowledge, f"""\
        # knowledge

        RULE: [{old_date}] Never skip tests
    """)

    memory.evict_old_entries(knowledge, archive, max_age_days=30)

    archived = archive.read_text(encoding="utf-8")
    # Both the pre-existing and newly archived content are present
    assert "Always use TDD" in archived
    assert "Never skip tests" in archived


# ── test_eviction_runs_in_meta ──────────────────────────────────────────
def test_eviction_runs_in_meta(tmp_path):
    """run_eviction() orchestrates both evictions given a memory_dir."""
    old_date = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
    recent_date = datetime.date.today().isoformat()

    mem = tmp_path / "memory"
    mem.mkdir()

    # knowledge.md with one old, one recent
    knowledge = mem / "knowledge.md"
    _write(knowledge, f"""\
        # knowledge

        RULE: [{old_date}] old rule

        RULE: [{recent_date}] new rule
    """)

    # activity_log.md with 35 entries (newest first)
    activity = mem / "activity_log.md"
    lines = ["# activity log\n"]
    for i in range(35, 0, -1):
        lines.append(f"\n## 2026-01-{i:02d} 10:00 — FEATURE\n")
        lines.append(f"DONE: Task {i}\nIMPACT: x\nFILES: f.py\n")
    activity.write_text("".join(lines), encoding="utf-8")

    result = memory.run_eviction(mem)

    # Returns a summary dict
    assert "knowledge_archived" in result
    assert "activity_archived" in result
    assert result["knowledge_archived"] > 0
    assert result["activity_archived"] > 0

    # Archives exist
    assert (mem / "knowledge_archive.md").exists()
    assert (mem / "activity_log_archive.md").exists()
