#!/usr/bin/env python3
"""Tests for registry.py — ProjectContext, register, get, list, remove, migrate."""
import json
import pytest
from pathlib import Path

import registry


@pytest.fixture(autouse=True)
def clean_agency(isolated_agency_home):
    """Reset agency state between tests."""
    home = isolated_agency_home
    # Create skills dir so migration can check it
    (home / "skills").mkdir(exist_ok=True)
    yield


@pytest.fixture
def fake_project(tmp_path):
    """Create a minimal fake project directory."""
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "src").mkdir()
    (proj / "tests").mkdir()
    (proj / ".gitignore").write_text("*.pyc\n")
    return proj


@pytest.fixture
def fake_v1(tmp_path, isolated_agency_home):
    """Create a minimal V1 autoagent directory inside a fake project."""
    proj = tmp_path / "myproject"
    proj.mkdir()
    v1 = proj / "autoagent"
    v1.mkdir()
    (v1 / "run.py").write_text("# V1 run.py stub")
    (v1 / "PROJECT.md").write_text("# My Project")
    (v1 / "NORTH_STAR.md").write_text("# North Star")
    (v1 / "sessions.json").write_text('[{"session": 1}]')
    mem = v1 / "memory"
    mem.mkdir()
    (mem / "backlog.md").write_text("- [ ] task 1")
    (mem / "activity_log.md").write_text("## session 1")
    skills = v1 / "skills"
    skills.mkdir()
    (skills / "coding.md").write_text("# Coding")  # universal — should NOT be copied
    (skills / "my-domain.md").write_text("# Domain")  # domain — SHOULD be copied
    # Put a universal skill in shared location so migration can detect overlap
    (isolated_agency_home / "skills" / "coding.md").write_text("# Shared coding")
    return proj, v1


# ── ProjectContext tests ──

def test_project_context_paths(isolated_agency_home):
    ctx = registry.ProjectContext(
        name="test",
        project_root=Path("/tmp/test"),
        agency_home=isolated_agency_home,
    )
    assert ctx.project_home == isolated_agency_home / "projects" / "test"
    assert ctx.memory_dir == ctx.project_home / "memory"
    assert ctx.agents_dir == ctx.project_home / "agents"
    assert ctx.sessions_file == ctx.project_home / "sessions.json"
    assert ctx.prompt_file == isolated_agency_home / "templates" / "PROMPT.md"
    assert ctx.meta_dir == isolated_agency_home / "templates" / "meta"


def test_project_context_skills_dirs(isolated_agency_home):
    ctx = registry.ProjectContext(
        name="test",
        project_root=Path("/tmp/test"),
        agency_home=isolated_agency_home,
    )
    dirs = ctx.skills_dirs()
    assert dirs[0] == isolated_agency_home / "skills"


def test_project_context_ensure_dirs(fake_project, isolated_agency_home):
    ctx = registry.ProjectContext(
        name="test",
        project_root=fake_project,
        agency_home=isolated_agency_home,
    )
    ctx.ensure_dirs()
    assert ctx.project_home.exists()
    assert ctx.memory_dir.exists()
    assert ctx.agents_dir.exists()
    assert (ctx.project_home / "skills").exists()


def test_project_context_symlink(fake_project, isolated_agency_home):
    ctx = registry.ProjectContext(
        name="test",
        project_root=fake_project,
        agency_home=isolated_agency_home,
    )
    ctx.ensure_dirs()
    ctx.ensure_symlink()
    link = fake_project / ".autoagent"
    assert link.is_symlink()
    assert link.resolve() == ctx.project_home.resolve()
    # .gitignore should have .autoagent
    assert ".autoagent" in (fake_project / ".gitignore").read_text()


def test_project_context_symlink_idempotent(fake_project, isolated_agency_home):
    ctx = registry.ProjectContext(
        name="test",
        project_root=fake_project,
        agency_home=isolated_agency_home,
    )
    ctx.ensure_dirs()
    ctx.ensure_symlink()
    ctx.ensure_symlink()  # should not raise
    assert (fake_project / ".autoagent").is_symlink()


def test_project_context_symlink_refuses_existing_file(fake_project, isolated_agency_home):
    """ensure_symlink refuses to delete a real project .autoagent file."""
    ctx = registry.ProjectContext(
        name="test",
        project_root=fake_project,
        agency_home=isolated_agency_home,
    )
    ctx.ensure_dirs()
    existing = fake_project / ".autoagent"
    existing.write_text("keep me")

    with pytest.raises(FileExistsError):
        ctx.ensure_symlink()

    assert existing.read_text() == "keep me"


# ── Register / Get / List / Remove ──

def test_register_creates_project(fake_project):
    ctx = registry.register("myproj", fake_project)
    assert ctx.name == "myproj"
    assert ctx.project_root == fake_project
    assert ctx.project_home.exists()
    assert ctx.memory_dir.exists()


def test_register_nonexistent_path_raises():
    with pytest.raises(FileNotFoundError):
        registry.register("bad", "/nonexistent/path")


def test_get_returns_project_context(fake_project):
    registry.register("myproj", fake_project)
    ctx = registry.get("myproj")
    assert ctx.name == "myproj"
    assert ctx.project_root == fake_project


def test_get_nonexistent_raises():
    with pytest.raises(KeyError):
        registry.get("nope")


def test_list_projects_empty():
    assert registry.list_projects() == []


def test_list_projects_returns_registered(fake_project):
    registry.register("myproj", fake_project)
    projects = registry.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "myproj"
    assert projects[0]["path"] == str(fake_project)


def test_remove_unregisters(fake_project):
    registry.register("myproj", fake_project)
    registry.remove("myproj")
    assert registry.list_projects() == []


def test_remove_nonexistent_is_noop():
    registry.remove("nope")  # should not raise


# ── Migrate V1 ──

def test_migrate_v1_copies_files(fake_v1):
    proj, v1 = fake_v1
    ctx = registry.migrate_v1(v1)
    # PROJECT.md should be copied
    assert (ctx.project_home / "PROJECT.md").exists()
    assert (ctx.project_home / "PROJECT.md").read_text() == "# My Project"
    # NORTH_STAR.md
    assert (ctx.project_home / "NORTH_STAR.md").exists()
    # sessions.json
    assert (ctx.project_home / "sessions.json").exists()


def test_migrate_v1_copies_memory(fake_v1):
    proj, v1 = fake_v1
    ctx = registry.migrate_v1(v1)
    assert (ctx.memory_dir / "backlog.md").exists()
    assert (ctx.memory_dir / "activity_log.md").exists()


def test_migrate_v1_separates_skills(fake_v1):
    proj, v1 = fake_v1
    ctx = registry.migrate_v1(v1)
    project_skills = ctx.project_home / "skills"
    # Domain skill should be in project skills
    assert (project_skills / "my-domain.md").exists()
    # Universal skill (coding.md) should NOT be in project skills
    assert not (project_skills / "coding.md").exists()


def test_migrate_v1_not_a_v1_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        registry.migrate_v1(tmp_path)


def test_migrate_v1_explicit_project_root(fake_v1):
    proj, v1 = fake_v1
    # Create a different project root
    other_root = proj.parent / "other_project"
    other_root.mkdir()
    ctx = registry.migrate_v1(v1, name="other", project_root=other_root)
    assert ctx.project_root == other_root
    assert ctx.name == "other"


# ── Config merging ──

def test_project_json_config_merges(fake_project):
    ctx = registry.register("myproj", fake_project)
    # Write a project.json with overrides
    pj = ctx.project_home / "project.json"
    pj.write_text(json.dumps({"daily_limit_usd": 42.0, "model": "claude-haiku-4-5"}))
    # Re-get should merge
    ctx2 = registry.get("myproj")
    assert ctx2.config["daily_limit_usd"] == 42.0
    assert ctx2.config["model"] == "claude-haiku-4-5"
    # Defaults should still be there for unset keys
    assert ctx2.config["session_max_turns"] == 50


# ── Cross-project skill sharing ──

def test_promote_skill_copies_to_shared(fake_project, isolated_agency_home):
    """promote_skill("myproj", "crop-analysis") copies to ~/.autoagent/skills/."""
    ctx = registry.register("myproj", fake_project)
    # Create a project-specific skill
    project_skills = ctx.project_home / "skills"
    project_skills.mkdir(exist_ok=True)
    (project_skills / "crop-analysis.md").write_text("# Crop Analysis\nNDVI thresholds...")

    registry.promote_skill("myproj", "crop-analysis")

    shared = isolated_agency_home / "skills" / "crop-analysis.md"
    assert shared.exists()
    assert "NDVI thresholds" in shared.read_text()


def test_promote_skill_nonexistent_raises(fake_project):
    """Promoting a skill that doesn't exist in the project raises FileNotFoundError."""
    registry.register("myproj", fake_project)
    with pytest.raises(FileNotFoundError):
        registry.promote_skill("myproj", "nonexistent")


def test_shared_skill_available_to_all_projects(fake_project, isolated_agency_home, tmp_path):
    """After promotion, all projects see the skill via all_skills()."""
    ctx_a = registry.register("proj_a", fake_project)
    # Create a second project
    proj_b_root = tmp_path / "proj_b"
    proj_b_root.mkdir()
    ctx_b = registry.register("proj_b", proj_b_root)

    # Create and promote a skill from proj_a
    project_skills = ctx_a.project_home / "skills"
    project_skills.mkdir(exist_ok=True)
    (project_skills / "special.md").write_text("# Special Skill")
    registry.promote_skill("proj_a", "special")

    # proj_b should now see the shared skill
    b_skill_names = [p.name for p in ctx_b.all_skills()]
    assert "special.md" in b_skill_names


def test_project_domain_shared_skill_hidden_by_default(fake_project, isolated_agency_home):
    """Manifest-scoped project-domain skills do not leak into generic projects."""
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "skill_scopes": {
            "universal": ["coding"],
            "project_domain": ["crop-analysis"],
        }
    }), encoding="utf-8")
    (isolated_agency_home / "skills" / "coding.md").write_text("# Coding", encoding="utf-8")
    (isolated_agency_home / "skills" / "crop-analysis.md").write_text("# Crop Analysis", encoding="utf-8")

    ctx = registry.register("generic", fake_project)
    assert [p.name for p in ctx.all_skills()] == ["coding.md"]


def test_project_domain_local_skill_remains_visible(fake_project, isolated_agency_home):
    """Project-local domain skills remain visible even when shared domain skills are hidden."""
    (isolated_agency_home / "templates" / "departments.json").write_text(json.dumps({
        "skill_scopes": {
            "universal": ["coding"],
            "project_domain": ["crop-analysis"],
        }
    }), encoding="utf-8")
    (isolated_agency_home / "skills" / "coding.md").write_text("# Coding", encoding="utf-8")
    (isolated_agency_home / "skills" / "crop-analysis.md").write_text("# Shared Crop", encoding="utf-8")

    ctx = registry.register("cultivos", fake_project)
    (ctx.project_home / "skills" / "crop-analysis.md").write_text("# Local Crop", encoding="utf-8")

    skills = {p.name: p for p in ctx.all_skills()}
    assert sorted(skills) == ["coding.md", "crop-analysis.md"]
    assert skills["crop-analysis.md"].read_text(encoding="utf-8") == "# Local Crop"


def test_knowledge_cross_pollination(fake_project, isolated_agency_home):
    """extract_universal_rules() finds rules without project-specific references."""
    ctx = registry.register("cultivOS", fake_project)
    knowledge = ctx.memory_dir / "knowledge.md"
    knowledge.write_text(
        "RULE: [2026-03-27] When testing CLI commands, patch on the cli module object\n"
        "RULE: [2026-03-27] cultivOS requires NDVI > 0.3 for healthy classification\n"
        "RULE: [2026-03-28] Always verify test counts by running the official command\n"
    )

    rules = registry.extract_universal_rules(ctx)

    # Should include generic rules but NOT the cultivOS-specific one
    assert len(rules) == 2
    assert any("CLI commands" in r for r in rules)
    assert any("test counts" in r for r in rules)
    assert not any("cultivOS" in r for r in rules)


# ── Validate project health ──

def test_validate_healthy_project(fake_project, isolated_agency_home):
    """A well-formed project with agents, backlog, and PROJECT.md returns no warnings."""
    ctx = registry.register("myproj", fake_project)
    ctx.ensure_dirs()
    # Create minimum healthy structure
    (ctx.agents_dir / "developer.md").write_text("# Developer\nBuilds features.")
    (ctx.memory_dir / "backlog.md").write_text("# Backlog\n- [ ] First task")
    (ctx.project_home / "PROJECT.md").write_text("# Project\n## Test Command\npytest")
    (ctx.project_home / "NORTH_STAR.md").write_text("# North Star\nShip it.")

    warnings = registry.validate_project(ctx)
    assert warnings == []


def test_validate_missing_agents(fake_project, isolated_agency_home):
    """Warns when agents dir is empty (no .md files)."""
    ctx = registry.register("myproj", fake_project)
    ctx.ensure_dirs()
    (ctx.memory_dir / "backlog.md").write_text("# Backlog\n- [ ] First task")
    (ctx.project_home / "PROJECT.md").write_text("# Project")
    (ctx.project_home / "NORTH_STAR.md").write_text("# North Star")

    warnings = registry.validate_project(ctx)
    assert any("agent" in w.lower() for w in warnings)


def test_validate_missing_backlog(fake_project, isolated_agency_home):
    """Warns when backlog.md is missing or has no unchecked items."""
    ctx = registry.register("myproj", fake_project)
    ctx.ensure_dirs()
    (ctx.agents_dir / "dev.md").write_text("# Dev")
    (ctx.project_home / "PROJECT.md").write_text("# Project")
    (ctx.project_home / "NORTH_STAR.md").write_text("# North Star")
    # No backlog.md at all

    warnings = registry.validate_project(ctx)
    assert any("backlog" in w.lower() for w in warnings)


# ── Registry split: registry_utils.py ──

def test_registry_under_300_lines():
    """registry.py must stay under 300 lines after extraction."""
    import inspect
    source_file = inspect.getfile(registry)
    line_count = len(Path(source_file).read_text().splitlines())
    assert line_count < 300, f"registry.py is {line_count} lines, must be < 300"


def test_promote_skill_from_new_module(fake_project, isolated_agency_home):
    """promote_skill is importable from registry_utils and works correctly."""
    import registry_utils
    ctx = registry.register("myproj", fake_project)
    project_skills = ctx.project_home / "skills"
    project_skills.mkdir(exist_ok=True)
    (project_skills / "my-skill.md").write_text("# My Skill\nContent here")

    registry_utils.promote_skill("myproj", "my-skill")

    shared = isolated_agency_home / "skills" / "my-skill.md"
    assert shared.exists()
    assert "Content here" in shared.read_text()
