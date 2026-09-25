"""Tests for self_improve_analyzers.py — cross-project sharing, metrics, skill gen, quality gate."""
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from self_improve_analyzers import (
    share_knowledge_across_projects,
    share_security_findings_across_projects,
    inject_production_metrics,
    generate_skill_from_knowledge,
    quality_gate_check,
)
from registry import ProjectContext


def _make_ctx(tmp_path, name="testproj"):
    agency_home = tmp_path / "agency"
    project_home = agency_home / "projects" / name
    project_home.mkdir(parents=True)
    mem = project_home / "memory"
    mem.mkdir()
    sf = project_home / "sessions.json"
    sf.write_text("[]", encoding="utf-8")
    return ProjectContext(
        name=name,
        project_root=tmp_path,
        agency_home=agency_home,
    )


def _make_multi_project(tmp_path, names, rules_map):
    """Create multiple projects with given knowledge rules.
    rules_map: {project_name: [list of RULE: lines]}
    Returns list of ProjectContext.
    """
    agency_home = tmp_path / "agency"
    ctxs = []
    for name in names:
        project_home = agency_home / "projects" / name
        project_home.mkdir(parents=True)
        mem = project_home / "memory"
        mem.mkdir()
        sf = project_home / "sessions.json"
        sf.write_text("[]", encoding="utf-8")
        if name in rules_map:
            kf = mem / "knowledge.md"
            kf.write_text("\n".join(rules_map[name]) + "\n", encoding="utf-8")
        ctx = ProjectContext(name=name, project_root=tmp_path, agency_home=agency_home)
        ctxs.append(ctx)
    return ctxs, agency_home


# ── share_knowledge_across_projects ────────────────────────────────

def test_cross_project_sharing_off_by_default(tmp_path, monkeypatch):
    # Tenant isolation: both share functions must no-op unless explicitly opted in.
    monkeypatch.delenv("AUTOAGENT_CROSS_PROJECT_SHARING", raising=False)
    with patch("self_improve_analyzers.list_projects",
               return_value=[{"name": "a"}, {"name": "b"}]):
        assert share_knowledge_across_projects() == 0
        assert share_security_findings_across_projects() == 0


class TestShareKnowledge:
    @pytest.fixture(autouse=True)
    def _enable_sharing(self, monkeypatch):
        # These tests exercise the sharing MECHANISM, which is gated off by
        # default — enable it so the mechanism runs.
        monkeypatch.setenv("AUTOAGENT_CROSS_PROJECT_SHARING", "1")

    def test_no_projects(self):
        with patch("self_improve_analyzers.list_projects", return_value=[]):
            assert share_knowledge_across_projects() == 0

    def test_single_project(self):
        with patch("self_improve_analyzers.list_projects", return_value=[{"name": "solo"}]):
            assert share_knowledge_across_projects() == 0

    def test_shares_universal_keyword_rules(self, tmp_path):
        ctxs, agency_home = _make_multi_project(tmp_path,
            ["projA", "projB"],
            {"projA": ["RULE: always run tests pass before merge"],
             "projB": []})

        def mock_list():
            return [{"name": "projA"}, {"name": "projB"}]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_knowledge_across_projects()

        assert shared >= 1
        kf_b = ctxs[1].memory_dir / "knowledge.md"
        assert kf_b.exists()
        content = kf_b.read_text(encoding="utf-8")
        assert "tests pass" in content.lower()

    def test_no_sharing_when_rules_already_exist(self, tmp_path):
        rule = "RULE: always run tests pass before merge"
        ctxs, _ = _make_multi_project(tmp_path,
            ["projA", "projB"],
            {"projA": [rule], "projB": [rule]})

        def mock_list():
            return [{"name": "projA"}, {"name": "projB"}]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_knowledge_across_projects()

        assert shared == 0

    def test_shares_duplicate_rules_across_projects(self, tmp_path):
        rule = "RULE: use feature flags for rollout"
        ctxs, _ = _make_multi_project(tmp_path,
            ["projA", "projB", "projC"],
            {"projA": [rule], "projB": [rule], "projC": []})

        def mock_list():
            return [{"name": n} for n in ["projA", "projB", "projC"]]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_knowledge_across_projects()

        assert shared >= 1
        kf_c = ctxs[2].memory_dir / "knowledge.md"
        assert "feature flags" in kf_c.read_text(encoding="utf-8").lower()


# ── share_security_findings_across_projects ────────────────────────

class TestShareSecurityFindings:
    @pytest.fixture(autouse=True)
    def _enable_sharing(self, monkeypatch):
        monkeypatch.setenv("AUTOAGENT_CROSS_PROJECT_SHARING", "1")

    def test_no_projects(self):
        with patch("self_improve_analyzers.list_projects", return_value=[]):
            assert share_security_findings_across_projects() == 0

    def test_single_project(self):
        with patch("self_improve_analyzers.list_projects", return_value=[{"name": "solo"}]):
            assert share_security_findings_across_projects() == 0

    def test_shares_security_findings(self, tmp_path):
        ctxs, _ = _make_multi_project(tmp_path,
            ["projA", "projB"],
            {"projA": ["RULE: SQL injection found in /api/users endpoint"],
             "projB": []})

        def mock_list():
            return [{"name": "projA"}, {"name": "projB"}]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_security_findings_across_projects()

        assert shared >= 1
        kf_b = ctxs[1].memory_dir / "knowledge.md"
        content = kf_b.read_text(encoding="utf-8")
        assert "injection" in content.lower()

    def test_does_not_share_non_security_rules(self, tmp_path):
        ctxs, _ = _make_multi_project(tmp_path,
            ["projA", "projB"],
            {"projA": ["RULE: use TDD for all features"],
             "projB": []})

        def mock_list():
            return [{"name": "projA"}, {"name": "projB"}]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_security_findings_across_projects()

        assert shared == 0

    def test_does_not_share_back_to_source(self, tmp_path):
        finding = "RULE: XSS vulnerability in form handler"
        ctxs, _ = _make_multi_project(tmp_path,
            ["projA", "projB"],
            {"projA": [finding], "projB": [finding]})

        def mock_list():
            return [{"name": "projA"}, {"name": "projB"}]

        def mock_get(name):
            return [c for c in ctxs if c.name == name][0]

        with patch("self_improve_analyzers.list_projects", side_effect=mock_list), \
             patch("self_improve_analyzers.get", side_effect=mock_get):
            shared = share_security_findings_across_projects()

        assert shared == 0


# ── inject_production_metrics ──────────────────────────────────────

class TestInjectProductionMetrics:
    def test_no_sessions_file(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.sessions_file.unlink()
        assert inject_production_metrics(ctx) == ""

    def test_empty_sessions(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        assert inject_production_metrics(ctx) == ""

    def test_malformed_json(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.sessions_file.write_text("NOT JSON", encoding="utf-8")
        assert inject_production_metrics(ctx) == ""

    def test_injects_metrics(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [
            {"session": i, "success": True, "quality": {"tests_after": 100 + i}}
            for i in range(10)
        ]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("# Knowledge\nRULE: something\n", encoding="utf-8")

        result = inject_production_metrics(ctx)
        assert "METRIC:" in result
        assert "100%" in result
        content = kf.read_text(encoding="utf-8")
        assert "METRIC:" in content

    def test_replaces_old_metrics(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [{"session": 1, "success": False, "quality": {"tests_after": 50}}]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("# Knowledge\nMETRIC: [old] stale\nRULE: keep this\n", encoding="utf-8")

        inject_production_metrics(ctx)
        content = kf.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.startswith("METRIC:")]
        assert len(lines) == 1
        assert "[old]" not in content

    def test_handles_missing_quality_field(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [{"session": 1}, {"session": 2}]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("# Knowledge\n", encoding="utf-8")

        result = inject_production_metrics(ctx)
        assert "METRIC:" in result


# ── generate_skill_from_knowledge ──────────────────────────────────

class TestGenerateSkill:
    def test_no_knowledge_file(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        assert generate_skill_from_knowledge(ctx) is None

    def test_too_few_rules(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("RULE: one\nRULE: two\n", encoding="utf-8")
        assert generate_skill_from_knowledge(ctx) is None

    def test_generates_skill_for_testing_topic(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        kf = ctx.memory_dir / "knowledge.md"
        rules = [
            "RULE: always run pytest before commit",
            "RULE: use test_ prefix for test files",
            "RULE: assert response status in tests",
            "RULE: use conftest.py for shared fixtures",
            "RULE: test_integration.py covers end-to-end",
        ]
        kf.write_text("\n".join(rules) + "\n", encoding="utf-8")
        result = generate_skill_from_knowledge(ctx)
        assert result == "testing"
        skill_file = ctx.project_home / "skills" / "testing.md"
        assert skill_file.exists()
        content = skill_file.read_text(encoding="utf-8")
        assert "Testing" in content

    def test_does_not_regenerate_existing_skill(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        kf = ctx.memory_dir / "knowledge.md"
        rules = [
            "RULE: always run pytest before commit",
            "RULE: use test_ prefix for test files",
            "RULE: assert response status in tests",
            "RULE: use conftest.py for shared fixtures",
            "RULE: test_integration.py covers end-to-end",
        ]
        kf.write_text("\n".join(rules) + "\n", encoding="utf-8")
        skills_dir = ctx.project_home / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "testing.md").write_text("existing", encoding="utf-8")
        assert generate_skill_from_knowledge(ctx) is None

    def test_no_matching_topics(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        kf = ctx.memory_dir / "knowledge.md"
        rules = [
            "RULE: generic rule one",
            "RULE: generic rule two",
            "RULE: generic rule three",
            "RULE: generic rule four",
            "RULE: generic rule five",
        ]
        kf.write_text("\n".join(rules) + "\n", encoding="utf-8")
        assert generate_skill_from_knowledge(ctx) is None


# ── quality_gate_check ─────────────────────────────────────────────

class TestQualityGate:
    def test_no_sessions_file(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.sessions_file.unlink()
        result = quality_gate_check(ctx)
        assert result["ok"] is True
        assert result["delta"] == 0

    def test_malformed_json(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.sessions_file.write_text("BROKEN", encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is True

    def test_single_session(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [{"session": 1, "quality": {"tests_after": 100}}]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is True

    def test_tests_increased(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [
            {"session": 1, "quality": {"tests_after": 100}},
            {"session": 2, "quality": {"tests_after": 110}},
        ]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is True
        assert result["delta"] == 10
        assert result["tests_before"] == 100
        assert result["tests_after"] == 110

    def test_tests_decreased_flags_failure(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [
            {"session": 1, "quality": {"tests_after": 100}},
            {"session": 2, "quality": {"tests_after": 90}},
        ]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("# Knowledge\n", encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is False
        assert result["delta"] == -10
        content = kf.read_text(encoding="utf-8")
        assert "QUALITY GATE" in content
        assert "TEST COUNT DROPPED" in content

    def test_tests_unchanged_is_ok(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [
            {"session": 1, "quality": {"tests_after": 100}},
            {"session": 2, "quality": {"tests_after": 100}},
        ]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is True
        assert result["delta"] == 0

    def test_missing_quality_field(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sessions = [{"session": 1}, {"session": 2}]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        result = quality_gate_check(ctx)
        assert result["ok"] is True
        assert result["tests_before"] == 0
        assert result["tests_after"] == 0
