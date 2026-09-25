"""Tests for constraint_checker — extract NEVER/ALWAYS/MUST rules and validate."""
import textwrap
from pathlib import Path

import pytest

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "constraint_checker", Path(__file__).parent / "constraint_checker.py"
)
constraint_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(constraint_checker)


def _write(path: Path, text: str):
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


# ── extract_constraints ──────────────────────────────────────────────


def test_extract_finds_never_rules(tmp_path):
    """NEVER lines are extracted with keyword, rule text, and source location."""
    md = tmp_path / "PROMPT.md"
    _write(md, """\
        # Rules
        - NEVER `git add autoagent/` from project root — it is in .gitignore
        - Some other line without a constraint
        - NEVER commit red tests
    """)
    rules = constraint_checker.extract_constraints(md)
    assert len(rules) == 2
    assert all(r["keyword"] == "NEVER" for r in rules)
    assert "git add autoagent" in rules[0]["rule"]
    assert rules[0]["source_file"] == str(md)
    assert isinstance(rules[0]["line_num"], int)


def test_extract_finds_always_rules(tmp_path):
    """ALWAYS lines are extracted."""
    md = tmp_path / "RULES.md"
    _write(md, """\
        ALWAYS run tests before committing.
        Some filler text.
        ALWAYS verify imports compile.
    """)
    rules = constraint_checker.extract_constraints(md)
    assert len(rules) == 2
    assert all(r["keyword"] == "ALWAYS" for r in rules)


def test_extract_finds_must_rules(tmp_path):
    """MUST lines are extracted."""
    md = tmp_path / "RULES.md"
    _write(md, """\
        You MUST update KEYS_NEEDED.md when adding API keys.
    """)
    rules = constraint_checker.extract_constraints(md)
    assert len(rules) == 1
    assert rules[0]["keyword"] == "MUST"


def test_extract_ignores_lowercase_keywords(tmp_path):
    """Only uppercase NEVER/ALWAYS/MUST are extracted (avoids false positives)."""
    md = tmp_path / "doc.md"
    _write(md, """\
        You should never do this casually.
        You must always be careful.
    """)
    rules = constraint_checker.extract_constraints(md)
    assert len(rules) == 0


def test_extract_from_nonexistent_file(tmp_path):
    """Returns empty list for missing files."""
    rules = constraint_checker.extract_constraints(tmp_path / "missing.md")
    assert rules == []


def test_extract_multiple_files(tmp_path):
    """extract_all_constraints scans a directory for .md files."""
    d = tmp_path / "prompts"
    d.mkdir()
    _write(d / "a.md", "NEVER delete production data\n")
    _write(d / "b.md", "ALWAYS backup before migration\n")
    _write(d / "c.txt", "NEVER match this — not .md\n")
    rules = constraint_checker.extract_all_constraints(d)
    assert len(rules) == 2
    keywords = {r["keyword"] for r in rules}
    assert keywords == {"NEVER", "ALWAYS"}


# ── check_file_constraints ──────────────────────────────────────────────


def test_check_detects_forbidden_path(tmp_path):
    """A NEVER rule mentioning a path pattern flags matching changed files."""
    rules = [
        {"keyword": "NEVER", "rule": "NEVER `git add autoagent/` from project root",
         "source_file": "PROMPT.md", "line_num": 5, "file_pattern": "autoagent/"}
    ]
    changed_files = ["autoagent/memory/backlog.md", "engine/run.py"]
    violations = constraint_checker.check_file_constraints(rules, changed_files)
    assert len(violations) == 1
    assert "autoagent/" in violations[0]["file"]
    assert violations[0]["rule"]["keyword"] == "NEVER"


def test_check_no_violations_when_clean(tmp_path):
    """No violations when changed files don't match any forbidden patterns."""
    rules = [
        {"keyword": "NEVER", "rule": "NEVER `git add autoagent/`",
         "source_file": "PROMPT.md", "line_num": 5, "file_pattern": "autoagent/"}
    ]
    changed_files = ["engine/run.py", "engine/test_run.py"]
    violations = constraint_checker.check_file_constraints(rules, changed_files)
    assert len(violations) == 0


def test_check_multiple_rules_multiple_violations():
    """Multiple rules can each produce violations."""
    rules = [
        {"keyword": "NEVER", "rule": "NEVER commit .env files",
         "source_file": "PROMPT.md", "line_num": 1, "file_pattern": ".env"},
        {"keyword": "NEVER", "rule": "NEVER commit secrets/",
         "source_file": "PROMPT.md", "line_num": 2, "file_pattern": "secrets/"},
    ]
    changed_files = [".env", "secrets/api_key.txt", "engine/run.py"]
    violations = constraint_checker.check_file_constraints(rules, changed_files)
    assert len(violations) == 2


# ── classify_constraint ──────────────────────────────────────────────


def test_classify_file_pattern_from_backticks():
    """Rules with backtick-wrapped paths get a file_pattern."""
    rule = {"keyword": "NEVER", "rule": "NEVER `git add autoagent/` from project root",
            "source_file": "x.md", "line_num": 1}
    classified = constraint_checker.classify_constraint(rule)
    assert classified.get("file_pattern") == "autoagent/"


def test_classify_behavioral_when_no_pattern():
    """Rules without detectable file patterns are classified as behavioral."""
    rule = {"keyword": "ALWAYS", "rule": "ALWAYS run tests before committing",
            "source_file": "x.md", "line_num": 1}
    classified = constraint_checker.classify_constraint(rule)
    assert classified.get("file_pattern") is None
    assert classified.get("type") == "behavioral"


# ── validate_session ──────────────────────────────────────────────


def test_validate_session_flags_commit_without_tests(tmp_path):
    """If PROMPT says NEVER commit red tests, and activity_log shows a session
    that committed with failing tests, validate_session flags it."""
    prompt = tmp_path / "PROMPT.md"
    _write(prompt, """\
        ## Hard Rules
        - NEVER commit red tests
        - ALWAYS run tests before committing
    """)
    activity = tmp_path / "activity_log.md"
    _write(activity, """\
        ## 2026-03-28 14:00 — FEATURE
        DONE: Added widget
        IMPACT: Users see widget
        FILES: engine/widget.py

        ## 2026-03-28 12:00 — FEATURE
        DONE: Committed without running tests — was in a hurry
        IMPACT: Broke the build
        FILES: engine/broken.py
    """)
    violations = constraint_checker.validate_session(prompt, activity)
    assert len(violations) >= 1
    # At least one violation should reference the session that mentions
    # "without running tests" against the "ALWAYS run tests" rule
    assert any("run tests" in v["rule"].lower() or "commit" in v["rule"].lower()
               for v in violations)


def test_validate_session_clean_log_no_violations(tmp_path):
    """A clean activity log produces no violations."""
    prompt = tmp_path / "PROMPT.md"
    _write(prompt, """\
        - NEVER commit red tests
    """)
    activity = tmp_path / "activity_log.md"
    _write(activity, """\
        ## 2026-03-28 14:00 — FEATURE
        DONE: Added widget with full test coverage
        IMPACT: Users see widget
        FILES: engine/widget.py
    """)
    violations = constraint_checker.validate_session(prompt, activity)
    assert len(violations) == 0


def test_validate_session_missing_files_returns_empty(tmp_path):
    """Missing prompt or activity log returns empty violations."""
    violations = constraint_checker.validate_session(
        tmp_path / "missing_prompt.md",
        tmp_path / "missing_activity.md"
    )
    assert violations == []


# ── auto_fix_test_count ──────────────────────────────────────────────


def test_auto_fix_stale_test_count(tmp_path):
    """When PROJECT.md says '100 tests must stay green' but actual count is 266,
    auto_fix_test_count updates the number."""
    project_md = tmp_path / "PROJECT.md"
    _write(project_md, """\
        # Project
        ## Hard Rules
        1. **TDD always**
        2. **100 tests must stay green** — never commit with failing tests
        ## Test Command
        ```
        echo dummy
        ```
    """)
    updated, old_count, new_count = constraint_checker.auto_fix_test_count(
        project_md, actual_count=266
    )
    assert updated is True
    assert old_count == 100
    assert new_count == 266
    text = project_md.read_text()
    assert "266 tests must stay green" in text
    assert "100 tests" not in text


def test_auto_fix_test_count_already_correct(tmp_path):
    """When PROJECT.md count matches actual, no update needed."""
    project_md = tmp_path / "PROJECT.md"
    _write(project_md, """\
        # Project
        ## Hard Rules
        1. **266 tests must stay green**
    """)
    updated, old_count, new_count = constraint_checker.auto_fix_test_count(
        project_md, actual_count=266
    )
    assert updated is False
    assert old_count == 266
    assert new_count == 266


def test_auto_fix_test_count_no_match(tmp_path):
    """When PROJECT.md has no 'N tests must stay green' line, returns not updated."""
    project_md = tmp_path / "PROJECT.md"
    _write(project_md, """\
        # Project
        No test count line here.
    """)
    updated, old_count, new_count = constraint_checker.auto_fix_test_count(
        project_md, actual_count=266
    )
    assert updated is False
    assert old_count is None
