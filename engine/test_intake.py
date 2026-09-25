#!/usr/bin/env python3
"""Tests for intake.py — project intake and team generation."""
import json
import re
import shutil
import pytest
from pathlib import Path

import registry


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    """Set up a minimal agency structure for each test."""
    home = isolated_agency_home
    # Extra dirs beyond conftest skeleton
    (home / "templates" / "examples").mkdir(parents=True, exist_ok=True)
    # Shared skills
    (home / "skills" / "coding.md").write_text("# Coding")
    (home / "skills" / "testing.md").write_text("# Testing")
    # Universal agent templates
    for agent in ["architect", "test-writer", "frontend", "infra", "ux-researcher", "educator"]:
        (home / "templates" / "agents" / f"{agent}.md").write_text(
            f"# {agent.replace('-', ' ').title()}\n\nYou are the {agent} for {{{{project_name}}}}.\n"
        )
    # INTAKE_PROMPT.md
    (home / "templates" / "INTAKE_PROMPT.md").write_text("# Intake prompt stub")
    # PROMPT.md template
    (home / "templates" / "PROMPT.md").write_text("# Universal PROMPT")
    (home / "templates" / "meta" / "PROMPT.md").write_text("# Meta prompt")
    (home / "templates" / "meta" / "BRAIN_PROMPT.md").write_text("# Brain prompt")
    yield


# ── Intake prompt exists and has required sections ──

def test_intake_prompt_exists(isolated_agency_home):
    path = isolated_agency_home / "templates" / "INTAKE_PROMPT.md"
    assert path.exists()


# ── Universal agent templates ──

def test_universal_agent_templates_exist(isolated_agency_home):
    agents_dir = isolated_agency_home / "templates" / "agents"
    expected = {"architect.md", "test-writer.md", "frontend.md", "infra.md", "ux-researcher.md", "educator.md"}
    actual = {f.name for f in agents_dir.glob("*.md")}
    assert expected.issubset(actual)


def test_universal_agent_templates_have_placeholder(isolated_agency_home):
    agents_dir = isolated_agency_home / "templates" / "agents"
    for f in agents_dir.glob("*.md"):
        content = f.read_text()
        assert "{{project_name}}" in content, f"{f.name} missing {{{{project_name}}}} placeholder"


# ── setup_project (the non-Claude part of intake) ──

import intake


def test_setup_project_creates_structure(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# Project: NewProject\n\nWe're building something cool.",
        north_star_md="# North Star\n\nGrow users.",
        backlog_md="- [ ] Build the thing\n- [ ] Test the thing",
    )
    assert ctx.project_home.exists()
    assert (ctx.project_home / "PROJECT.md").read_text().startswith("# Project: NewProject")
    assert (ctx.project_home / "NORTH_STAR.md").read_text().startswith("# North Star")
    assert (ctx.memory_dir / "backlog.md").read_text().startswith("- [ ] Build")


def test_setup_project_copies_universal_agents(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    agents = list(ctx.agents_dir.glob("*.md"))
    agent_names = {a.name for a in agents}
    assert "architect.md" in agent_names
    assert "test-writer.md" in agent_names
    assert "frontend.md" in agent_names


def test_setup_project_skips_duplicate_agent_templates(tmp_path, isolated_agency_home):
    agents_dir = isolated_agency_home / "templates" / "agents"
    (agents_dir / "architect 2.md").write_text(
        "# Architect Copy\n\nYou are a duplicate for {{project_name}}.\n",
        encoding="utf-8",
    )
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    assert (ctx.agents_dir / "architect.md").exists()
    assert not (ctx.agents_dir / "architect 2.md").exists()


def test_setup_project_replaces_placeholder_in_agents(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    arch = (ctx.agents_dir / "architect.md").read_text()
    assert "newproject" in arch
    assert "{{project_name}}" not in arch


def test_setup_project_adds_domain_agents(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    domain_agents = {
        "crop-analyst": "# Crop Analyst\n\nYou analyze crops.",
        "agronomist": "# Agronomist\n\nYou recommend treatments.",
    }
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
        domain_agents=domain_agents,
    )
    assert (ctx.agents_dir / "crop-analyst.md").exists()
    assert (ctx.agents_dir / "agronomist.md").exists()
    assert "analyze crops" in (ctx.agents_dir / "crop-analyst.md").read_text()


def test_setup_project_creates_orchestrator(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    domain_agents = {"analyst": "# Analyst\nYou analyze."}
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
        domain_agents=domain_agents,
    )
    orch = ctx.agents_dir / "orchestrator.md"
    assert orch.exists()
    content = orch.read_text()
    assert "analyst" in content.lower()
    assert "architect" in content.lower()


def test_setup_project_initializes_memory(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    assert (ctx.memory_dir / "current_task.md").exists()
    assert (ctx.memory_dir / "activity_log.md").exists()
    assert (ctx.memory_dir / "knowledge.md").exists()
    assert (ctx.memory_dir / "done.md").exists()


def test_setup_project_registers_in_agency(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    projects = registry.list_projects()
    assert any(p["name"] == "newproject" for p in projects)


def test_setup_project_creates_symlink(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
    )
    assert (project_root / ".autoagent").is_symlink()


def test_setup_project_creates_project_json(tmp_path):
    project_root = tmp_path / "newproject"
    project_root.mkdir()
    ctx = intake.setup_project(
        name="newproject",
        project_root=project_root,
        project_md="# P",
        north_star_md="# N",
        backlog_md="# B",
        tech_stack="Python/FastAPI",
        test_command="pytest tests/ -q",
    )
    pj = ctx.project_home / "project.json"
    assert pj.exists()
    data = json.loads(pj.read_text())
    assert data["tech_stack"] == "Python/FastAPI"
    assert data["test_command"] == "pytest tests/ -q"


# ── _consume_staging — reads staging dir and calls setup_project ──


def _make_staging(base_dir: Path, project_root: Path, manifest_overrides=None):
    """Helper to create a realistic staging directory."""
    staging = base_dir / "projects" / "_intake_staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "memory").mkdir(exist_ok=True)
    (staging / "agents").mkdir(exist_ok=True)

    manifest = {
        "name": "testproj",
        "project_path": str(project_root),
        "tech_stack": "Python/FastAPI",
        "test_command": "pytest tests/ -q",
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (staging / "PROJECT.md").write_text("# Project: TestProj\n\nBuilding a test app.")
    (staging / "NORTH_STAR.md").write_text("# North Star\n\nGrow users.")
    (staging / "memory" / "backlog.md").write_text("- [ ] Build login\n- [ ] Build dashboard")
    (staging / "agents" / "domain-expert.md").write_text("# Domain Expert\n\nYou know things.")
    return staging


def test_consume_staging_returns_project_context(tmp_path, isolated_agency_home):
    """Staging with valid manifest -> returns ProjectContext with correct name."""
    project_root = tmp_path / "myrepo"
    project_root.mkdir()
    _make_staging(isolated_agency_home, project_root)

    ctx = intake._consume_staging()
    assert ctx is not None
    assert ctx.name == "testproj"
    assert (ctx.project_home / "PROJECT.md").exists()
    assert (ctx.project_home / "NORTH_STAR.md").exists()
    assert (ctx.memory_dir / "backlog.md").exists()


def test_consume_staging_passes_domain_agents(tmp_path, isolated_agency_home):
    """Domain agents from staging/agents/ are passed to setup_project."""
    project_root = tmp_path / "myrepo"
    project_root.mkdir()
    _make_staging(isolated_agency_home, project_root)

    ctx = intake._consume_staging()
    assert ctx is not None
    assert (ctx.agents_dir / "domain-expert.md").exists()
    content = (ctx.agents_dir / "domain-expert.md").read_text()
    assert "You know things" in content


def test_consume_staging_missing_manifest(isolated_agency_home):
    """No manifest.json in staging -> returns None."""
    staging = isolated_agency_home / "projects" / "_intake_staging"
    staging.mkdir(parents=True, exist_ok=True)
    # No manifest.json written
    (staging / "PROJECT.md").write_text("# P")

    result = intake._consume_staging()
    assert result is None


def test_consume_staging_no_staging_dir(isolated_agency_home):
    """No staging dir at all -> returns None."""
    staging = isolated_agency_home / "projects" / "_intake_staging"
    if staging.exists():
        shutil.rmtree(staging)

    result = intake._consume_staging()
    assert result is None


def test_consume_staging_cleans_up(tmp_path, isolated_agency_home):
    """After successful consumption, staging dir is removed."""
    project_root = tmp_path / "myrepo"
    project_root.mkdir()
    staging = _make_staging(isolated_agency_home, project_root)

    ctx = intake._consume_staging()
    assert ctx is not None
    assert not staging.exists(), "Staging directory should be removed after consumption"


# ── Intake prompt quality — validates the REAL template ──

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_INTAKE_PROMPT = _REPO_ROOT / "templates" / "INTAKE_PROMPT.md"


def test_intake_prompt_no_jargon():
    """INTAKE_PROMPT.md contains zero instances of developer jargon in questions."""
    content = _REAL_INTAKE_PROMPT.read_text(encoding="utf-8")
    jargon_terms = ["endpoint", "middleware", "ORM", "schema", "microservice"]
    found = [t for t in jargon_terms if re.search(rf"\b{t}\b", content, re.IGNORECASE)]
    assert found == [], f"INTAKE_PROMPT.md contains developer jargon: {found}"


def test_generated_backlog_plain_language():
    """Backlog generation rules require user's own words, not developer terminology."""
    content = _REAL_INTAKE_PROMPT.read_text(encoding="utf-8")
    # The prompt must instruct Claude to use the user's language in backlog tasks
    assert "user's words" in content.lower() or "user's language" in content.lower() or "their words" in content.lower(), \
        "INTAKE_PROMPT.md must instruct backlog generation to use the user's own words"


def test_intake_asks_about_users():
    """Interview questions ask about who uses it, not just tech stack."""
    content = _REAL_INTAKE_PROMPT.read_text(encoding="utf-8")
    # Must ask about users/audience before or instead of tech stack as a primary question
    assert "who will use" in content.lower() or "who are the users" in content.lower() or "who has this problem" in content.lower(), \
        "INTAKE_PROMPT.md must ask about users/audience"
    # Tech stack question should not be a primary interview question
    # (it can exist as a secondary/optional question)


def test_consume_staging_passes_tech_stack_and_test_command(tmp_path, isolated_agency_home):
    """Tech stack and test command from manifest are passed to setup_project."""
    project_root = tmp_path / "myrepo"
    project_root.mkdir()
    _make_staging(isolated_agency_home, project_root)

    ctx = intake._consume_staging()
    pj = ctx.project_home / "project.json"
    data = json.loads(pj.read_text())
    assert data["tech_stack"] == "Python/FastAPI"
    assert data["test_command"] == "pytest tests/ -q"
