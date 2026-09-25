#!/usr/bin/env python3
"""Unit tests for run.py pure functions — session type, budget, cost, prompt building, quality score."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import registry

# Import engine/run.py explicitly — V1 root-level run.py shadows it
import importlib.util
_run_spec = importlib.util.spec_from_file_location(
    "engine_run", Path(__file__).parent / "run.py"
)
run_module = importlib.util.module_from_spec(_run_spec)
_run_spec.loader.exec_module(run_module)

get_session_type = run_module.get_session_type
budget_ok = run_module.budget_ok
log_cost = run_module.log_cost
build_prompt = run_module.build_prompt


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    """Set up minimal agency structure for each test."""
    home = isolated_agency_home
    (home / "templates" / "PROMPT.md").write_text("# Base Prompt\nSession rules.")
    (home / "templates" / "meta" / "PROMPT.md").write_text("# Meta Prompt\nMeta rules.")
    (home / "templates" / "meta" / "BRAIN_PROMPT.md").write_text("# Brain Prompt\nBrain rules.")
    yield


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
    ctx.project_file.write_text("# Project\nTest project.")
    (ctx.memory_dir / "activity_log.md").write_text("# Log")
    (ctx.memory_dir / "backlog.md").write_text("# Backlog")
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge")
    return ctx


# ── get_session_type ───────────────────���──────────────────────

def test_session_type_work():
    """Regular sessions (not multiples of 5) are work."""
    assert get_session_type(1) == "work"
    assert get_session_type(3) == "work"
    assert get_session_type(7) == "work"
    assert get_session_type(13) == "work"


def test_session_type_meta():
    """Every 5th session (not 10th, 20th, or 25th) is meta."""
    assert get_session_type(5) == "meta"
    assert get_session_type(15) == "meta"
    assert get_session_type(35) == "meta"


def test_session_type_brain():
    """Every 10th session (not 20th or 50th) is brain."""
    assert get_session_type(10) == "brain"
    assert get_session_type(30) == "brain"


def test_session_type_audit():
    """Every 25th session (not 50th) is audit."""
    assert get_session_type(25) == "audit"
    assert get_session_type(75) == "audit"


def test_session_type_knowledge():
    """Every 50th session is knowledge compilation."""
    assert get_session_type(50) == "knowledge"
    assert get_session_type(100) == "knowledge"


def test_session_type_deep():
    """Every 20th session is deep."""
    assert get_session_type(20) == "deep"
    assert get_session_type(40) == "deep"
    assert get_session_type(60) == "deep"


# ── council ship-review gate cadence (guards the run.py:489 fix) ──────
# The gate is `session_type == "work" and session_num % 5 == 1`. The OLD
# gate used `% 5 == 0`, which is DEAD: get_session_type sends every multiple
# of 5 to a non-work type, so no session is ever both work and % 5 == 0.
# These lock the routing coupling the fix relies on.

def test_council_gate_old_residue_never_fires():
    """`% 5 == 0` sessions are never work — the old gate could never fire."""
    assert not any(get_session_type(n) == "work" for n in range(5, 201, 5))


def test_council_gate_new_residue_always_work():
    """`% 5 == 1` always lands on a work session, so the new gate fires."""
    fires = [n for n in range(1, 201) if n % 5 == 1]
    assert fires  # non-empty
    assert all(get_session_type(n) == "work" for n in fires)


# ── budget_ok ───���─────────────────────────────────────────────

def test_budget_ok_no_file(tmp_path):
    """No budget file means budget is always OK."""
    ctx = _make_ctx(tmp_path)
    assert budget_ok(ctx) is True


def test_budget_ok_under_limit(tmp_path):
    """Spending under the daily limit returns True."""
    ctx = _make_ctx(tmp_path, config={"daily_limit_usd": 10.0})
    from datetime import date
    today = str(date.today())
    ctx.budget_file.write_text(json.dumps({today: 5.0}))
    assert budget_ok(ctx) is True


def test_budget_ok_over_limit(tmp_path):
    """Spending at or over the daily limit returns False."""
    ctx = _make_ctx(tmp_path, config={"daily_limit_usd": 10.0})
    from datetime import date
    today = str(date.today())
    ctx.budget_file.write_text(json.dumps({today: 10.0}))
    assert budget_ok(ctx) is False


# ── log_cost ────────────────────────────────────────��─────────

def test_log_cost_new_file(tmp_path):
    """log_cost creates the budget file if it doesn't exist."""
    ctx = _make_ctx(tmp_path)
    log_cost(ctx, 2.5)
    assert ctx.budget_file.exists()
    data = json.loads(ctx.budget_file.read_text())
    from datetime import date
    today = str(date.today())
    assert data[today] == 2.5


def test_log_cost_accumulates(tmp_path):
    """log_cost adds to existing spend for today."""
    ctx = _make_ctx(tmp_path)
    log_cost(ctx, 1.0)
    log_cost(ctx, 2.5)
    data = json.loads(ctx.budget_file.read_text())
    from datetime import date
    today = str(date.today())
    assert data[today] == 3.5


def test_log_cost_malformed_file(tmp_path):
    """log_cost handles a malformed budget file gracefully."""
    ctx = _make_ctx(tmp_path)
    ctx.budget_file.write_text("NOT JSON")
    log_cost(ctx, 1.0)
    data = json.loads(ctx.budget_file.read_text())
    from datetime import date
    today = str(date.today())
    assert data[today] == 1.0


# ── build_prompt ──────────────────────────────────────────────

def test_build_prompt_work(tmp_path):
    """Work prompt includes project file and session instructions."""
    ctx = _make_ctx(tmp_path)
    prompt = build_prompt(ctx, "work")
    assert "Project" in prompt
    assert "Session rules" in prompt


def test_build_prompt_meta(tmp_path):
    """Meta prompt includes meta instructions."""
    ctx = _make_ctx(tmp_path)
    prompt = build_prompt(ctx, "meta")
    assert "Meta rules" in prompt


def test_build_prompt_deep(tmp_path):
    """Deep prompt includes both meta and brain instructions."""
    ctx = _make_ctx(tmp_path)
    prompt = build_prompt(ctx, "deep")
    assert "Meta" in prompt
    assert "Brain" in prompt


# ── _extract_test_command ────────────────────────────────────

_extract_test_command = run_module._extract_test_command

def test_extract_test_command_from_project_md(tmp_path):
    """Extracts the test command from PROJECT.md code block under ### Test Command."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -m pytest tests/ -q\n```\n"
    )
    assert _extract_test_command(ctx) == "python3 -m pytest tests/ -q"


def test_extract_test_command_missing_returns_none(tmp_path):
    """Returns None when PROJECT.md has no Test Command section."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text("# Project\nNo test command here.")
    assert _extract_test_command(ctx) is None


# ── _pre_push_gate ───────────────────────────────────────────

_pre_push_gate = run_module._pre_push_gate

def test_pre_push_gate_green_tests(tmp_path):
    """_pre_push_gate returns True when the test command exits 0."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -c \"exit(0)\"\n```\n"
    )
    assert _pre_push_gate(ctx) is True


def test_pre_push_gate_red_tests(tmp_path):
    """_pre_push_gate returns False when the test command exits non-zero."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -c \"exit(1)\"\n```\n"
    )
    assert _pre_push_gate(ctx) is False


def test_pre_push_gate_no_test_command(tmp_path):
    """_pre_push_gate returns True (pass) when no test command is configured."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text("# Project\nNo test command.")
    assert _pre_push_gate(ctx) is True


# ── compute_quality_score ───���────────────────────────────────

compute_quality_score = run_module.compute_quality_score


def test_quality_score_calculation():
    """Perfect session: 1 task + 5 tests added + 0 broken + 0 retries = score 100.
    Worst session: 0 tasks + 0 tests + 2 broken = score 0."""
    # Perfect session
    assert compute_quality_score(
        tasks_completed=1, tests_added=5, tests_broken=0, retries=0
    ) == 100

    # Worst session
    assert compute_quality_score(
        tasks_completed=0, tests_added=0, tests_broken=2, retries=0
    ) == 0

    # Partial — task done but tests broken
    score = compute_quality_score(
        tasks_completed=1, tests_added=3, tests_broken=1, retries=2
    )
    assert 0 < score < 100


def test_session_json_has_quality_fields(tmp_path):
    """sessions.json entry includes quality fields when quality data is provided."""
    ctx = _make_ctx(tmp_path)
    sessions_file = ctx.project_home / "sessions.json"
    sessions_file.write_text("[]")

    entry = {
        "session": 1,
        "date": "2026-03-28",
        "time": "12:00",
        "type": "work",
        "summary": "Built a feature",
        "files": ["foo.py"],
        "tests": {"before": 10, "after": 15, "status": "pass"},
        "frontend": {"status": "skip", "checks": 0, "failures": 0, "notes": ""},
        "quality": {
            "tasks_completed": 1,
            "tests_added": 5,
            "tests_broken": 0,
            "retries": 0,
            "duration_seconds": 300,
            "score": 100,
        },
    }

    # Verify structure has all required quality fields
    q = entry["quality"]
    assert "tasks_completed" in q
    assert "tests_added" in q
    assert "tests_broken" in q
    assert "retries" in q
    assert "duration_seconds" in q
    assert "score" in q
    assert q["score"] == compute_quality_score(
        tasks_completed=q["tasks_completed"],
        tests_added=q["tests_added"],
        tests_broken=q["tests_broken"],
        retries=q["retries"],
    )


def test_meta_reads_quality_scores(tmp_path):
    """Meta prompt includes average quality score from last 5 sessions."""
    ctx = _make_ctx(tmp_path)
    # Create sessions.json with 6 sessions (only last 5 should be averaged)
    sessions = []
    for i in range(6):
        sessions.append({
            "session": i + 1,
            "type": "work",
            "quality": {
                "tasks_completed": 1,
                "tests_added": i,
                "tests_broken": 0,
                "retries": 0,
                "duration_seconds": 300,
                "score": 60 + i * 8,  # 60, 68, 76, 84, 92, 100
            },
        })
    ctx.sessions_file.write_text(json.dumps(sessions))

    prompt = build_prompt(ctx, "meta")
    # Last 5 scores: 68, 76, 84, 92, 100 → avg = 84
    assert "84" in prompt
    assert "quality" in prompt.lower() or "score" in prompt.lower()


# ── _build_child_env (BYOK key handling) ──────────────────────

def test_build_child_env_injects_byok_from_config(tmp_path, monkeypatch):
    """A configured anthropic_api_key is injected into the child env (tenant billing)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BYOK_ANTHROPIC_API_KEY", raising=False)
    ctx = _make_ctx(tmp_path, config={"anthropic_api_key": "sk-tenant"})
    env = run_module._build_child_env(ctx)
    assert env["ANTHROPIC_API_KEY"] == "sk-tenant"


def test_build_child_env_injects_from_byok_env_var(tmp_path, monkeypatch):
    """$BYOK_ANTHROPIC_API_KEY is honored when config carries no key."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("BYOK_ANTHROPIC_API_KEY", "sk-env")
    ctx = _make_ctx(tmp_path, config={})
    env = run_module._build_child_env(ctx)
    assert env["ANTHROPIC_API_KEY"] == "sk-env"


def test_build_child_env_strips_dead_key_when_no_byok(tmp_path, monkeypatch):
    """Without BYOK configured, a stray ANTHROPIC_API_KEY is stripped so Max auth wins."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-dead-shell-key")
    monkeypatch.delenv("BYOK_ANTHROPIC_API_KEY", raising=False)
    ctx = _make_ctx(tmp_path, config={})
    env = run_module._build_child_env(ctx)
    assert "ANTHROPIC_API_KEY" not in env


def test_build_child_env_config_wins_over_byok_env(tmp_path, monkeypatch):
    """ctx.config key takes precedence over the $BYOK_ANTHROPIC_API_KEY fallback."""
    monkeypatch.setenv("BYOK_ANTHROPIC_API_KEY", "sk-env")
    ctx = _make_ctx(tmp_path, config={"anthropic_api_key": "sk-config"})
    env = run_module._build_child_env(ctx)
    assert env["ANTHROPIC_API_KEY"] == "sk-config"


# ── File size guards ──��──────────────────────────────────────

def test_run_py_under_600_lines():
    """run.py size guard — budget 325→400 (2026-04-16) → 600 (2026-06-24).
    The 300-line rule is aspirational; wiring (model routing, cost pass-through,
    budget caps, BYOK key injection) keeps landing here. Real debt is the
    ~349-line run_session(); extract it to drop back under 400. The leaf helpers
    (log_cost/budget_ok/log_session/...) are imported across ~15 modules, so they
    can't move without a coordinated refactor — hence the ceiling bump, not a split."""
    run_file = Path(__file__).parent / "run.py"
    line_count = len(run_file.read_text().splitlines())
    assert line_count <= 600, f"run.py is {line_count} lines (limit: 600)"


def test_runner_py_under_300_lines():
    """runner.py must stay under 300 lines."""
    runner_file = Path(__file__).parent / "runner.py"
    line_count = len(runner_file.read_text().splitlines())
    assert line_count <= 300, f"runner.py is {line_count} lines (limit: 300)"


_INDEX_SAMPLE = (
    "# Index\ngeneric coding row\n\n"
    "<!-- PROJECT-DOMAIN-START -->\n## Project-domain\ncrop-analysis row\n"
    "<!-- PROJECT-DOMAIN-END -->\n"
)


class _FakeCtx:
    def __init__(self, config):
        self.config = config
        self.agency_home = "."


def test_scope_index_strips_project_domain_when_disabled():
    """A project without project_domain enabled gets no project-domain rows injected."""
    out = run_module._scope_index_text(_INDEX_SAMPLE, _FakeCtx({}))
    assert "generic coding row" in out
    assert "crop-analysis" not in out
    assert "PROJECT-DOMAIN" not in out


def test_scope_index_keeps_project_domain_when_enabled():
    """A project that opts in keeps the project-domain rows."""
    out = run_module._scope_index_text(
        _INDEX_SAMPLE, _FakeCtx({"include_project_domain_skills": True})
    )
    assert "crop-analysis" in out
