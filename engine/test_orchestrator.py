#!/usr/bin/env python3
"""Tests for orchestrator.py — agent routing, task parsing, prompt building."""
import json
import pytest
from pathlib import Path

import registry


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    """Set up a minimal agency with one project and agents."""
    home = isolated_agency_home
    (home / "templates" / "PROMPT.md").write_text("# Work rules")
    (home / "templates" / "meta" / "PROMPT.md").write_text("# Meta rules")
    (home / "templates" / "meta" / "BRAIN_PROMPT.md").write_text("# Brain rules")
    # Copy ORCHESTRATOR_PROMPT.md from real templates dir
    _real_template = Path(__file__).parent.parent / "templates" / "ORCHESTRATOR_PROMPT.md"
    if _real_template.exists():
        (home / "templates" / "ORCHESTRATOR_PROMPT.md").write_text(
            _real_template.read_text(encoding="utf-8")
        )
    (home / "skills" / "coding.md").write_text("# Coding")
    yield


@pytest.fixture
def project_with_agents(tmp_path):
    """Register a project with agent definitions and a backlog."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    ctx = registry.register("testproj", proj)
    ctx.ensure_dirs()

    # Write agents
    agents = {
        "crop-analyst": "# Crop Analyst\nYou analyze NDVI and health scores.",
        "agronomist": "# Agronomist\nYou recommend organic treatments.",
        "data-engineer": "# Data Engineer\nYou build data pipelines.",
        "architect": "# Architect\nYou oversee code quality.",
    }
    for name, content in agents.items():
        (ctx.agents_dir / f"{name}.md").write_text(content)

    # Write PROJECT.md and NORTH_STAR.md
    (ctx.project_home / "PROJECT.md").write_text("# Test Project")
    (ctx.project_home / "NORTH_STAR.md").write_text("# North Star")

    # Write backlog with agent hints
    (ctx.memory_dir / "backlog.md").write_text(
        "# Backlog\n\n"
        "### 1. Thermal stress detection [agent: crop-analyst]\n"
        "- Test: test_thermal_hot_zones\n\n"
        "### 2. Treatment recommendation [agent: agronomist]\n"
        "- Test: test_low_ndvi_recommends_treatment\n\n"
        "### 3. Image pipeline [agent: data-engineer]\n"
        "- Test: test_ingest_validates_format\n\n"
        "### 4. Refactor DB models\n"
        "- Test: test_models_import\n"
    )
    (ctx.memory_dir / "current_task.md").write_text("# Current Task: (none)\n")
    (ctx.memory_dir / "activity_log.md").write_text("# Activity Log\n")
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n")
    return ctx


import orchestrator


# ── Parse agent hint from backlog ──

def test_parse_agent_hint_from_task():
    line = "### 1. Thermal stress detection [agent: crop-analyst]"
    assert orchestrator.parse_agent_hint(line) == "crop-analyst"


def test_parse_agent_hint_missing():
    line = "### 4. Refactor DB models"
    assert orchestrator.parse_agent_hint(line) is None


def test_parse_agent_hint_various_formats():
    assert orchestrator.parse_agent_hint("[agent: data-engineer] Build pipeline") == "data-engineer"
    assert orchestrator.parse_agent_hint("Task name [agent:agronomist]") == "agronomist"


# ── List available agents ──

def test_list_agents(project_with_agents):
    agents = orchestrator.list_agents(project_with_agents)
    names = {a["name"] for a in agents}
    assert "crop-analyst" in names
    assert "agronomist" in names
    assert "architect" in names
    assert "data-engineer" in names


def test_list_agents_includes_description(project_with_agents):
    agents = orchestrator.list_agents(project_with_agents)
    crop = next(a for a in agents if a["name"] == "crop-analyst")
    assert "NDVI" in crop["description"] or "Crop Analyst" in crop["description"]


def test_list_agents_empty_dir(tmp_path):
    proj = tmp_path / "empty"
    proj.mkdir()
    ctx = registry.register("empty", proj)
    ctx.ensure_dirs()
    assert orchestrator.list_agents(ctx) == []


# ── Load agent prompt ──

def test_load_agent_prompt(project_with_agents):
    prompt = orchestrator.load_agent_prompt(project_with_agents, "crop-analyst")
    assert "NDVI" in prompt
    assert "Crop Analyst" in prompt


def test_load_agent_prompt_missing_returns_empty(project_with_agents):
    prompt = orchestrator.load_agent_prompt(project_with_agents, "nonexistent")
    assert prompt == ""


# ── Build agent-scoped boot prompt ──

def test_build_agent_boot_prompt(project_with_agents):
    boot = orchestrator.build_agent_boot_prompt(project_with_agents, "crop-analyst", "work")
    assert "crop-analyst" in boot
    assert "testproj" in boot
    assert ".autoagent" in boot


def test_build_agent_boot_prompt_no_agent(project_with_agents):
    boot = orchestrator.build_agent_boot_prompt(project_with_agents, None, "work")
    assert "crop-analyst" not in boot
    # Should still have basic instructions
    assert ".autoagent" in boot


def test_build_agent_boot_prompt_audit_uses_existing_security_skills(project_with_agents):
    boot = orchestrator.build_agent_boot_prompt(project_with_agents, "security-auditor", "audit")
    assert ".autoagent/skills/security.md" in boot
    assert ".autoagent/skills/audit.md" in boot
    assert "security-audit.md" not in boot


# ── Parse orchestrator output ──

def test_parse_orchestrator_output_structured():
    output = "TASK: Thermal stress detection\nAGENT: crop-analyst\nREASON: NDVI analysis task"
    result = orchestrator.parse_orchestrator_output(output)
    assert result["task"] == "Thermal stress detection"
    assert result["agent"] == "crop-analyst"


def test_parse_orchestrator_output_no_agent():
    output = "TASK: General refactoring\nAGENT: none\nREASON: No specialist needed"
    result = orchestrator.parse_orchestrator_output(output)
    assert result["task"] == "General refactoring"
    assert result["agent"] is None


def test_parse_orchestrator_output_malformed():
    output = "I'll work on the thermal stress task using the crop analyst agent."
    result = orchestrator.parse_orchestrator_output(output)
    # Should handle gracefully — extract what it can
    assert result["task"] is not None or result["agent"] is not None or result == {"task": None, "agent": None}


# ── Orchestrator prompt template ──

def test_orchestrator_prompt_file_exists(isolated_agency_home):
    """templates/ORCHESTRATOR_PROMPT.md exists on disk."""
    path = isolated_agency_home / "templates" / "ORCHESTRATOR_PROMPT.md"
    assert path.exists(), f"ORCHESTRATOR_PROMPT.md not found at {path}"


def test_orchestrator_prompt_has_format_spec(isolated_agency_home):
    """Template contains TASK:, AGENT:, REASON: format specification."""
    path = isolated_agency_home / "templates" / "ORCHESTRATOR_PROMPT.md"
    content = path.read_text(encoding="utf-8")
    assert "TASK:" in content, "Template must contain TASK: format spec"
    assert "AGENT:" in content, "Template must contain AGENT: format spec"
    assert "REASON:" in content, "Template must contain REASON: format spec"


def test_orchestrator_prompt_loads_from_template():
    """build_orchestrator_prompt uses the template file content."""
    prompt = orchestrator.build_orchestrator_prompt(None)
    assert "TASK:" in prompt
    assert "AGENT:" in prompt
    assert "REASON:" in prompt
    assert "backlog" in prompt.lower()


def test_orchestrator_prompt_with_ctx_includes_agent_roster(project_with_agents):
    """build_orchestrator_prompt(ctx) injects agent roster table when agents exist."""
    prompt = orchestrator.build_orchestrator_prompt(project_with_agents)
    assert "Available agents" in prompt
    assert "crop-analyst" in prompt
    assert "agronomist" in prompt
    assert "data-engineer" in prompt
    assert "architect" in prompt
    # Should be a markdown table
    assert "| Agent |" in prompt


# ── DAG-aware ready tasks ──

def test_get_ready_tasks_returns_unblocked(project_with_agents):
    """get_ready_tasks returns only tasks whose deps are satisfied."""
    bl = project_with_agents.memory_dir / "backlog.md"
    bl.write_text(
        "- [x] [T1] Setup database\n"
        "- [ ] [T2] Build API (depends: T1)\n"
        "- [ ] [T3] Wire frontend (depends: T1, T2)\n"
    )
    ready = orchestrator.get_ready_tasks(project_with_agents)
    ids = [t["id"] for t in ready]
    assert "T2" in ids
    assert "T3" not in ids  # T2 not done yet


def test_get_ready_tasks_empty_backlog(project_with_agents):
    bl = project_with_agents.memory_dir / "backlog.md"
    bl.write_text("")
    assert orchestrator.get_ready_tasks(project_with_agents) == []


def test_orchestrator_prompt_includes_ready_tasks(project_with_agents):
    """build_orchestrator_prompt injects ready tasks table when deps exist."""
    bl = project_with_agents.memory_dir / "backlog.md"
    bl.write_text(
        "- [x] [T1] Setup\n"
        "- [ ] [T2] Build API (depends: T1) [agent: data-engineer]\n"
    )
    prompt = orchestrator.build_orchestrator_prompt(project_with_agents)
    assert "Ready tasks" in prompt
    assert "T2" in prompt
    assert "Build API" in prompt


# ── Agent-described generation (user tells us what agent they need) ──

def test_generate_agent_from_description():
    content = orchestrator.generate_agent_md(
        name="soil-scientist",
        description="Analyzes soil composition, recommends amendments, tracks pH and nutrients over time",
        project_name="cultivOS",
    )
    assert "# Soil Scientist" in content or "# soil-scientist" in content.lower()
    assert "cultivOS" in content
    assert "soil" in content.lower()


def test_generate_agent_from_description_has_sections():
    content = orchestrator.generate_agent_md(
        name="payment-engineer",
        description="Handles Stripe integration, subscription management, invoice generation",
        project_name="SaaSApp",
    )
    assert "responsibility" in content.lower() or "role" in content.lower()


# ── _detect_agent (from run.py) ──
# Import run.py via importlib to avoid V1 root-level run.py shadow
import importlib.util
_run_spec = importlib.util.spec_from_file_location("engine_run", Path(__file__).parent / "run.py")
_run_mod = importlib.util.module_from_spec(_run_spec)
_run_spec.loader.exec_module(_run_mod)
_detect_agent = _run_mod._detect_agent


def test_detect_agent_from_backlog(project_with_agents):
    """_detect_agent reads [agent: X] from top backlog task."""
    result = _detect_agent(project_with_agents, "work")
    assert result == "crop-analyst"  # first task hint in backlog


def test_detect_agent_from_current_task(project_with_agents):
    """_detect_agent reads AGENT: X from current_task.md."""
    ct = project_with_agents.memory_dir / "current_task.md"
    ct.write_text("# Current Task: Treatment plan\nAGENT: agronomist\n- [ ] Step 1\n")
    result = _detect_agent(project_with_agents, "work")
    assert result == "agronomist"


def test_detect_agent_skips_nonexistent(project_with_agents):
    """Hint for agent without .md file returns None."""
    # Overwrite backlog with a hint pointing to a non-existent agent
    bl = project_with_agents.memory_dir / "backlog.md"
    bl.write_text(
        "# Backlog\n\n"
        "### 1. Some task [agent: ghost-agent]\n"
        "- Test: test_something\n"
    )
    # Clear current_task so it doesn't match
    ct = project_with_agents.memory_dir / "current_task.md"
    ct.write_text("# Current Task: (none)\n")
    result = _detect_agent(project_with_agents, "work")
    assert result is None


# ── Module size constraint ──

def test_orchestrator_under_300_lines():
    """orchestrator.py stays under 300-line hard limit after extraction."""
    orch_file = Path(__file__).parent / "orchestrator.py"
    line_count = len(orch_file.read_text(encoding="utf-8").splitlines())
    assert line_count < 300, f"orchestrator.py is {line_count} lines (limit: 300)"


# ── agent_utils module ──

def test_generate_agent_from_new_module():
    """generate_agent_md is importable from agent_utils (the new home)."""
    import agent_utils
    content = agent_utils.generate_agent_md(
        name="soil-scientist",
        description="Analyzes soil composition",
        project_name="cultivOS",
    )
    assert "Soil Scientist" in content
    assert "cultivOS" in content


def test_list_agents_from_new_module(project_with_agents):
    """list_agents is importable from agent_utils."""
    import agent_utils
    agents = agent_utils.list_agents(project_with_agents)
    names = {a["name"] for a in agents}
    assert "crop-analyst" in names


# ── Auto-backlog generation ──

def test_auto_backlog_skips_when_enough(project_with_agents):
    """auto_generate_backlog returns [] when backlog has ≥3 unchecked items."""
    # project_with_agents fixture already writes 4 unchecked tasks
    items = orchestrator.auto_generate_backlog(project_with_agents)
    assert items == []


def test_auto_backlog_generates_items(tmp_path, isolated_agency_home):
    """auto_generate_backlog scans for test gaps and generates EARS items."""
    # Set up a project with a nearly-empty backlog and some Python modules
    proj = tmp_path / "scanproj"
    proj.mkdir()
    ctx = registry.register("scanproj", proj)
    ctx.ensure_dirs()

    # Write a near-empty backlog (only 1 unchecked item)
    (ctx.memory_dir / "backlog.md").write_text(
        "# Backlog\n\n- [ ] One remaining task\n"
    )

    # Write PROJECT.md with a test command
    (ctx.project_home / "PROJECT.md").write_text(
        "# Project\n\n### Test Command\n```\npython3 -m pytest tests/ -q\n```\n"
    )

    # Write NORTH_STAR.md
    (ctx.project_home / "NORTH_STAR.md").write_text(
        "# North Star\n\n| Metric | Current | Target |\n"
        "|--------|---------|--------|\n"
        "| Tests passing | 5 | 50 |\n"
    )

    # Create some Python modules in the project root
    (proj / "app.py").write_text("def main(): pass\n")
    (proj / "utils.py").write_text("def helper(): pass\n")
    # Only one test file with few tests
    tests_dir = proj / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "def test_main(): pass\n"
    )
    # utils.py has NO test file at all

    items = orchestrator.auto_generate_backlog(ctx)
    assert len(items) >= 1
    # Each item should have EARS-quality: trigger word (When/If) and a test name
    for item in items:
        assert any(kw in item for kw in ("When ", "If ", "While ")), \
            f"Item lacks EARS trigger: {item}"
        assert "test_" in item.lower(), f"Item lacks test name: {item}"


def test_auto_backlog_ears_quality(tmp_path, isolated_agency_home):
    """Generated items have quantified scope (files to change)."""
    proj = tmp_path / "earsproj"
    proj.mkdir()
    ctx = registry.register("earsproj", proj)
    ctx.ensure_dirs()

    (ctx.memory_dir / "backlog.md").write_text("# Backlog\n")
    (ctx.project_home / "PROJECT.md").write_text("# Project\n")
    (ctx.project_home / "NORTH_STAR.md").write_text("# North Star\n")

    # Create modules without tests
    (proj / "server.py").write_text("def serve(): pass\n")
    (proj / "models.py").write_text("class User: pass\n")

    items = orchestrator.auto_generate_backlog(ctx)
    assert len(items) >= 1
    # Each item should mention files to change
    for item in items:
        assert "File" in item or "file" in item, \
            f"Item lacks file scope: {item}"


# ── recite_todos — KV-cache friendly todo recital ────────────────────

def test_recital_appends_to_tail():
    """recite_todos appends a formatted todo block to prompt tail."""
    prompt = "You are working on project X."
    todos = ["Fix auth bug", "Add tests for login"]
    result = orchestrator.recite_todos(prompt, todos)
    assert result.startswith(prompt)
    assert result.endswith("\n")
    assert "Fix auth bug" in result
    assert "Add tests for login" in result
    tail = result[len(prompt):]
    assert "OPEN ITEMS" in tail or "TODO" in tail


def test_recital_no_mutation():
    """recite_todos returns new string, never mutates input."""
    prompt = "Original prompt."
    todos = ["Task A"]
    original_prompt = prompt
    original_todos = todos.copy()
    result = orchestrator.recite_todos(prompt, todos)
    assert prompt == original_prompt
    assert todos == original_todos
    assert result != prompt
    assert result is not prompt


def test_recital_empty_todos_returns_prompt_unchanged():
    """recite_todos with empty list returns prompt as-is."""
    prompt = "Working on something."
    result = orchestrator.recite_todos(prompt, [])
    assert result == prompt


def test_append_only_context_invariant():
    """append_context only adds to tail, never modifies prior content."""
    base = "System prompt line 1.\nLine 2."
    turn1 = orchestrator.append_context(base, "User asked about auth.")
    assert turn1.startswith(base)
    assert "auth" in turn1
    turn2 = orchestrator.append_context(turn1, "Agent found a bug in login.")
    assert turn2.startswith(turn1)
    assert "login" in turn2
    assert turn2[:len(turn1)] == turn1
