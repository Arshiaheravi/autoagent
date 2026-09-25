"""Tests for agent_memory.py — technique storage and retrieval."""
import json
import pytest
from registry import ProjectContext
import agent_memory as am


@pytest.fixture
def ctx(tmp_path):
    """Minimal ProjectContext with agents_dir writable."""
    c = ProjectContext(
        name="test",
        project_root=tmp_path / "project",
        agency_home=tmp_path / "agency",
    )
    c.project_home.mkdir(parents=True, exist_ok=True)
    c.agents_dir.mkdir(parents=True, exist_ok=True)
    return c


# ── record_technique ──


def test_record_technique_stores_entry(ctx):
    """record_technique stores a structured technique entry in agent memory."""
    am.record_technique(
        ctx, "developer", technique="TDD with pure functions",
        files_affected=["run.py", "helpers.py"], success=True, session_num=42,
    )
    mem = am.load_agent_memory(ctx, "developer")
    techniques = mem.get("techniques", [])
    assert len(techniques) == 1
    t = techniques[0]
    assert t["technique"] == "TDD with pure functions"
    assert t["files_affected"] == ["run.py", "helpers.py"]
    assert t["success"] is True
    assert t["session_num"] == 42


def test_record_technique_appends_multiple(ctx):
    """Multiple techniques accumulate, not overwrite."""
    am.record_technique(ctx, "developer", technique="A", files_affected=[], success=True, session_num=1)
    am.record_technique(ctx, "developer", technique="B", files_affected=[], success=False, session_num=2)
    mem = am.load_agent_memory(ctx, "developer")
    assert len(mem["techniques"]) == 2
    assert mem["techniques"][0]["technique"] == "A"
    assert mem["techniques"][1]["technique"] == "B"


def test_record_technique_dedup(ctx):
    """Duplicate technique text is not stored twice."""
    am.record_technique(ctx, "developer", technique="Same thing", files_affected=[], success=True, session_num=1)
    am.record_technique(ctx, "developer", technique="Same thing", files_affected=[], success=True, session_num=2)
    mem = am.load_agent_memory(ctx, "developer")
    assert len(mem["techniques"]) == 1


def test_record_technique_max_limit(ctx):
    """Techniques list is capped at _MAX_TECHNIQUES."""
    for i in range(20):
        am.record_technique(ctx, "developer", technique=f"tech_{i}", files_affected=[], success=True, session_num=i)
    mem = am.load_agent_memory(ctx, "developer")
    assert len(mem["techniques"]) <= am._MAX_TECHNIQUES


def test_techniques_empty_by_default(ctx):
    """Fresh agent memory has empty techniques list."""
    mem = am.load_agent_memory(ctx, "developer")
    assert mem.get("techniques", []) == []


# ── inject_agent_memory_context with techniques ──


def test_technique_retrieved_in_context(ctx):
    """inject_agent_memory_context includes successful techniques."""
    # Need at least one session for context to be non-empty
    am.update_agent_memory(ctx, "developer", session_num=1, success=True, summary="built feature")
    am.record_technique(ctx, "developer", technique="Pure function pattern", files_affected=["run.py"], success=True, session_num=1)
    context = am.inject_agent_memory_context(ctx, "developer", max_chars=2000)
    assert "Pure function pattern" in context
    assert "Techniques" in context or "technique" in context.lower()


def test_technique_context_omits_failed(ctx):
    """inject_agent_memory_context only shows successful techniques."""
    am.update_agent_memory(ctx, "developer", session_num=1, success=True, summary="built feature")
    am.record_technique(ctx, "developer", technique="Bad approach", files_affected=[], success=False, session_num=1)
    am.record_technique(ctx, "developer", technique="Good approach", files_affected=[], success=True, session_num=2)
    context = am.inject_agent_memory_context(ctx, "developer", max_chars=2000)
    assert "Good approach" in context
    assert "Bad approach" not in context
