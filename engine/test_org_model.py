#!/usr/bin/env python3
"""Tests for department organization model."""
import json

import org_model


def test_universal_templates_follow_manifest(isolated_agency_home):
    agents_dir = isolated_agency_home / "templates" / "agents"
    (agents_dir / "architect.md").write_text("# Architect\n\n{{project_name}}", encoding="utf-8")
    (agents_dir / "frontend.md").write_text("# Frontend\n\n{{project_name}}", encoding="utf-8")
    (agents_dir / "architect 2.md").write_text("# Duplicate\n\n{{project_name}}", encoding="utf-8")
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "departments": [
            {
                "id": "engineering",
                "name": "Engineering",
                "agents": [
                    {"name": "architect", "scope": "universal", "template": True},
                    {"name": "missing-agent", "scope": "universal", "template": True},
                    {"name": "director", "scope": "runtime", "template": False},
                ],
                "skills": [],
                "loops": ["work"],
            }
        ]
    }), encoding="utf-8")

    paths = org_model.universal_agent_template_paths(isolated_agency_home)
    assert [p.name for p in paths] == ["architect.md"]

    report = org_model.build_org_report(isolated_agency_home)
    assert "missing-agent" in report["missing_agent_templates"]
    assert "architect 2.md" in report["duplicate_agent_templates"]
    assert "frontend" in report["unmanaged_agent_templates"]


def test_format_org_report_lists_departments(isolated_agency_home):
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "departments": [
            {"id": "engineering", "name": "Engineering", "agents": [], "skills": [], "loops": ["cleanup"]}
        ],
        "candidate_agents": [
            {"name": "technical-writer", "department": "growth-comms", "reason": "Docs"}
        ],
    }), encoding="utf-8")
    report = org_model.build_org_report(isolated_agency_home)
    text = org_model.format_org_report(report)
    assert "Engineering" in text
    assert "cleanup" in text
    assert "technical-writer" in text


def test_project_domain_shared_skills_are_notes_not_strict_errors(isolated_agency_home):
    skills_dir = isolated_agency_home / "skills"
    (skills_dir / "coding.md").write_text("# Coding", encoding="utf-8")
    (skills_dir / "crop-analysis.md").write_text("# Crop Analysis", encoding="utf-8")
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "departments": [
            {"id": "engineering", "name": "Engineering", "agents": [], "skills": ["coding"], "loops": []}
        ],
        "skill_scopes": {
            "universal": ["coding"],
            "project_domain": ["crop-analysis"],
        },
    }), encoding="utf-8")

    report = org_model.build_org_report(isolated_agency_home)
    assert report["strict_ok"] is True
    assert report["errors"] == []
    assert report["project_domain_skills_in_shared"] == ["crop-analysis"]
    assert "crop-analysis" not in report["visible_shared_skills"]
    assert any("hidden by default" in note for note in report["notes"])


def test_visible_skill_paths_hide_project_domain_unless_enabled(isolated_agency_home, tmp_path):
    skills_dir = isolated_agency_home / "skills"
    (skills_dir / "coding.md").write_text("# Coding", encoding="utf-8")
    (skills_dir / "crop-analysis.md").write_text("# Crop Analysis", encoding="utf-8")
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "skill_scopes": {
            "universal": ["coding"],
            "project_domain": ["crop-analysis"],
        },
    }), encoding="utf-8")

    class Ctx:
        name = "proj"
        agency_home = isolated_agency_home
        project_home = tmp_path / "proj_autoagent"
        config = {}

    Ctx.project_home.mkdir()
    (Ctx.project_home / "skills").mkdir()
    assert [p.name for p in org_model.visible_skill_paths(Ctx)] == ["coding.md"]

    (Ctx.project_home / "skills" / "crop-analysis.md").write_text("# Local Crop", encoding="utf-8")
    assert [p.name for p in org_model.visible_skill_paths(Ctx)] == ["coding.md", "crop-analysis.md"]

    (Ctx.project_home / "skills" / "crop-analysis.md").unlink()
    Ctx.config = {"include_project_domain_skills": True}
    assert [p.name for p in org_model.visible_skill_paths(Ctx)] == ["coding.md", "crop-analysis.md"]
