#!/usr/bin/env python3
"""Unit tests for self_improve_analyzers.py — pure analysis functions."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import registry


@pytest.fixture(autouse=True)
def _enable_cross_project_sharing(monkeypatch):
    """Cross-project rule/finding sharing is gated off by default (tenant
    isolation). This file's tests exercise the sharing mechanism, so enable it."""
    monkeypatch.setenv("AUTOAGENT_CROSS_PROJECT_SHARING", "1")


@pytest.fixture(autouse=True)
def isolated_agency_home(tmp_path, monkeypatch):
    """Isolate AGENCY_HOME so tests don't touch real data."""
    home = tmp_path / "agency"
    home.mkdir()
    (home / "templates").mkdir(parents=True)
    (home / "templates" / "agents").mkdir(parents=True)
    monkeypatch.setattr(registry, "AGENCY_HOME", home)
    (home / "agency.json").write_text(json.dumps({"projects": {}, "defaults": {}}))
    return home


def _make_ctx(tmp_path, name="testproj", config=None):
    """Create a ProjectContext with project dirs set up."""
    ctx = registry.ProjectContext(
        name=name,
        project_root=tmp_path / name,
        agency_home=registry.AGENCY_HOME,
        config=config or {},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.project_home.mkdir(parents=True, exist_ok=True)
    ctx.memory_dir.mkdir(parents=True, exist_ok=True)
    (ctx.project_home / "skills").mkdir(parents=True, exist_ok=True)
    ctx.sessions_file.parent.mkdir(parents=True, exist_ok=True)
    return ctx


# ── share_knowledge_across_projects ─────────────────────────────

def test_share_knowledge_needs_two_projects(tmp_path):
    """Returns 0 when fewer than 2 projects exist."""
    from self_improve_analyzers import share_knowledge_across_projects
    # Register only 1 project
    ctx = _make_ctx(tmp_path, "solo")
    registry.register(ctx.name, str(ctx.project_root))
    assert share_knowledge_across_projects() == 0


def test_share_knowledge_copies_universal_rules(tmp_path):
    """Universal-keyword rules from one project are shared to another."""
    from self_improve_analyzers import share_knowledge_across_projects
    ctx1 = _make_ctx(tmp_path, "proj1")
    ctx2 = _make_ctx(tmp_path, "proj2")
    registry.register(ctx1.name, str(ctx1.project_root))
    registry.register(ctx2.name, str(ctx2.project_root))
    # Write a universal rule in proj1
    (ctx1.memory_dir / "knowledge.md").write_text("RULE: always run tests pass before commit\n")
    (ctx2.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    shared = share_knowledge_across_projects()
    assert shared >= 1
    content = (ctx2.memory_dir / "knowledge.md").read_text()
    assert "always run tests pass" in content.lower()


# ── inject_production_metrics ───────────────────────────────────

def test_inject_metrics_no_sessions(tmp_path):
    """Returns empty string when no sessions.json exists."""
    from self_improve_analyzers import inject_production_metrics
    ctx = _make_ctx(tmp_path, "empty")
    assert inject_production_metrics(ctx) == ""


def test_inject_metrics_writes_to_knowledge(tmp_path):
    """Writes METRIC line to knowledge.md from session data."""
    from self_improve_analyzers import inject_production_metrics
    ctx = _make_ctx(tmp_path, "metriced")
    sessions = [{"quality": {"tests_after": 50, "score": 80}} for _ in range(3)]
    ctx.sessions_file.write_text(json.dumps(sessions))
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    result = inject_production_metrics(ctx)
    assert result.startswith("METRIC:")
    content = (ctx.memory_dir / "knowledge.md").read_text()
    assert "METRIC:" in content


# ── generate_skill_from_knowledge ───────────────────────────────

def test_generate_skill_no_rules(tmp_path):
    """Returns None when knowledge.md has fewer than 5 rules."""
    from self_improve_analyzers import generate_skill_from_knowledge
    ctx = _make_ctx(tmp_path, "norules")
    (ctx.memory_dir / "knowledge.md").write_text("RULE: one\nRULE: two\n")
    assert generate_skill_from_knowledge(ctx) is None


def test_generate_skill_creates_file(tmp_path):
    """Creates a skill .md file when 3+ rules match a topic."""
    from self_improve_analyzers import generate_skill_from_knowledge
    ctx = _make_ctx(tmp_path, "skillgen")
    rules = "\n".join([
        "RULE: always run test_foo before committing",
        "RULE: use pytest fixtures for test_ setup",
        "RULE: assert test_ output matches expected",
        "RULE: conftest.py defines shared fixtures",
        "RULE: pytest -x stops on first failure",
    ])
    (ctx.memory_dir / "knowledge.md").write_text(rules)
    result = generate_skill_from_knowledge(ctx)
    assert result == "testing"
    skill_file = ctx.project_home / "skills" / "testing.md"
    assert skill_file.exists()


# ── quality_gate_check ──────────────────────────────────────────

def test_quality_gate_no_sessions(tmp_path):
    """Returns ok=True when no sessions exist."""
    from self_improve_analyzers import quality_gate_check
    ctx = _make_ctx(tmp_path, "nogate")
    result = quality_gate_check(ctx)
    assert result["ok"] is True


def test_quality_gate_detects_drop(tmp_path):
    """Flags ok=False when test count drops between sessions."""
    from self_improve_analyzers import quality_gate_check
    ctx = _make_ctx(tmp_path, "dropped")
    sessions = [
        {"session": 1, "quality": {"tests_after": 100}},
        {"session": 2, "quality": {"tests_after": 90}},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions))
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    result = quality_gate_check(ctx)
    assert result["ok"] is False
    assert result["delta"] == -10


def test_quality_gate_passes_on_increase(tmp_path):
    """Returns ok=True when test count increases."""
    from self_improve_analyzers import quality_gate_check
    ctx = _make_ctx(tmp_path, "grew")
    sessions = [
        {"session": 1, "quality": {"tests_after": 50}},
        {"session": 2, "quality": {"tests_after": 60}},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions))
    result = quality_gate_check(ctx)
    assert result["ok"] is True
    assert result["delta"] == 10


# ── backward-compatible re-export from self_improve ─────────────

def test_self_improve_reexports_analyzers():
    """All 4 analyzer functions are importable from self_improve."""
    from self_improve import (
        share_knowledge_across_projects,
        inject_production_metrics,
        generate_skill_from_knowledge,
        quality_gate_check,
    )
    assert callable(share_knowledge_across_projects)
    assert callable(inject_production_metrics)
    assert callable(generate_skill_from_knowledge)
    assert callable(quality_gate_check)


# ── post_session_improve ───────────────────────────────────────

def test_post_session_improve_returns_dict(tmp_path):
    """post_session_improve returns a dict with quality_gate and metrics keys."""
    from self_improve import post_session_improve
    ctx = _make_ctx(tmp_path, "postproj")
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    result = post_session_improve(ctx)
    assert isinstance(result, dict)
    assert "quality_gate" in result
    assert "metrics" in result


def test_post_session_improve_quality_gate_ok_no_sessions(tmp_path):
    """post_session_improve quality_gate is ok when no sessions exist."""
    from self_improve import post_session_improve
    ctx = _make_ctx(tmp_path, "emptysess")
    result = post_session_improve(ctx)
    assert result["quality_gate"]["ok"] is True


def test_post_session_improve_metrics_empty_no_sessions(tmp_path):
    """post_session_improve metrics is empty string when no sessions."""
    from self_improve import post_session_improve
    ctx = _make_ctx(tmp_path, "nometric")
    result = post_session_improve(ctx)
    assert result["metrics"] == ""


def test_post_session_improve_with_sessions(tmp_path):
    """post_session_improve processes sessions and returns metrics."""
    from self_improve import post_session_improve
    ctx = _make_ctx(tmp_path, "withsess")
    sessions = [
        {"session": 1, "quality": {"tests_after": 50, "score": 80}},
        {"session": 2, "quality": {"tests_after": 55, "score": 85}},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions))
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    # Mock the rubric LLM call — otherwise post_session_improve spawns a real
    # `claude -p` subprocess (nested-claude latency ~2 min, needs live auth),
    # which has no place in a unit test.
    with patch("judge._call_judge_llm", return_value={"score": 8, "reason": "mocked"}):
        result = post_session_improve(ctx)
    assert result["quality_gate"]["ok"] is True
    assert result["quality_gate"]["delta"] == 5
    assert "METRIC:" in result["metrics"]
    # Judge ran on the mocked call and its timing was recorded.
    assert result["judge"]["verdict"] == "ACCEPT"
    assert "elapsed_s" in result["judge"]
    verdict_line = json.loads(
        (ctx.memory_dir / "judge_verdicts.jsonl").read_text().strip().splitlines()[-1]
    )
    assert "judge_elapsed_s" in verdict_line


# ── generate_skill edge cases ─────────────────────────────────

def test_generate_skill_no_knowledge_file(tmp_path):
    """Returns None when knowledge.md doesn't exist."""
    from self_improve_analyzers import generate_skill_from_knowledge
    ctx = _make_ctx(tmp_path, "nofile")
    (ctx.memory_dir / "knowledge.md").unlink(missing_ok=True)
    assert generate_skill_from_knowledge(ctx) is None


def test_generate_skill_skips_existing(tmp_path):
    """Returns None when the skill file already exists."""
    from self_improve_analyzers import generate_skill_from_knowledge
    ctx = _make_ctx(tmp_path, "exists")
    rules = "\n".join([
        "RULE: always run test_foo before committing",
        "RULE: use pytest fixtures for test_ setup",
        "RULE: assert test_ output matches expected",
        "RULE: conftest.py defines shared fixtures",
        "RULE: pytest -x stops on first failure",
    ])
    (ctx.memory_dir / "knowledge.md").write_text(rules)
    # Pre-create the skill file
    skill_dir = ctx.project_home / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "testing.md").write_text("# existing")
    assert generate_skill_from_knowledge(ctx) is None


# ── share_security_findings_across_projects ────────────────────

def test_cross_project_vuln_sharing_needs_two_projects(tmp_path):
    """Returns 0 when fewer than 2 projects exist."""
    from self_improve_analyzers import share_security_findings_across_projects
    ctx = _make_ctx(tmp_path, "solo")
    registry.register(ctx.name, str(ctx.project_root))
    assert share_security_findings_across_projects() == 0


def test_cross_project_vuln_sharing(tmp_path):
    """Security findings from one project are shared to others."""
    from self_improve_analyzers import share_security_findings_across_projects
    ctx1 = _make_ctx(tmp_path, "proj_a")
    ctx2 = _make_ctx(tmp_path, "proj_b")
    registry.register(ctx1.name, str(ctx1.project_root))
    registry.register(ctx2.name, str(ctx2.project_root))
    # Write a security finding in proj_a's knowledge
    (ctx1.memory_dir / "knowledge.md").write_text(
        "RULE: [SECURITY] SQL injection found in user_input route — always parameterize queries\n"
        "RULE: [SECURITY] XSS vulnerability in dashboard render — escape all user HTML\n"
        "RULE: some non-security rule\n"
    )
    (ctx2.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    shared = share_security_findings_across_projects()
    assert shared >= 2
    content = (ctx2.memory_dir / "knowledge.md").read_text()
    assert "sql injection" in content.lower()
    assert "xss" in content.lower()
    # Non-security rule should NOT be shared
    assert "non-security rule" not in content.lower()


def test_cross_project_vuln_sharing_no_duplicates(tmp_path):
    """Does not re-share findings that already exist in the target project."""
    from self_improve_analyzers import share_security_findings_across_projects
    ctx1 = _make_ctx(tmp_path, "src_proj")
    ctx2 = _make_ctx(tmp_path, "dst_proj")
    registry.register(ctx1.name, str(ctx1.project_root))
    registry.register(ctx2.name, str(ctx2.project_root))
    finding = "RULE: [SECURITY] SQL injection in user_input — parameterize queries\n"
    (ctx1.memory_dir / "knowledge.md").write_text(finding)
    (ctx2.memory_dir / "knowledge.md").write_text(finding)  # Already has it
    shared = share_security_findings_across_projects()
    assert shared == 0


def test_cross_project_vuln_sharing_reexport():
    """share_security_findings_across_projects is importable from self_improve."""
    from self_improve import share_security_findings_across_projects
    assert callable(share_security_findings_across_projects)


# ── quality_gate edge cases ───────────────────────────────────

def test_quality_gate_single_session(tmp_path):
    """Returns ok=True when only 1 session exists (can't compare)."""
    from self_improve_analyzers import quality_gate_check
    ctx = _make_ctx(tmp_path, "single")
    ctx.sessions_file.write_text(json.dumps([{"session": 1, "quality": {"tests_after": 50}}]))
    result = quality_gate_check(ctx)
    assert result["ok"] is True


def test_quality_gate_non_numeric_tests(tmp_path):
    """Handles non-numeric tests_after gracefully."""
    from self_improve_analyzers import quality_gate_check
    ctx = _make_ctx(tmp_path, "baddata")
    sessions = [
        {"session": 1, "quality": {"tests_after": "fifty"}},
        {"session": 2, "quality": {"tests_after": "sixty"}},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions))
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    result = quality_gate_check(ctx)
    # Both non-numeric → treated as 0, delta=0, ok=True
    assert result["ok"] is True
    assert result["delta"] == 0
