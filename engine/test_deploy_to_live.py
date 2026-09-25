"""Tests for scripts/deploy_to_live.py — repo → ~/.autoagent sync."""
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

dtl = pytest.importorskip("deploy_to_live")


def _fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "engine").mkdir(parents=True)
    (repo / "engine" / "run.py").write_text("NEW ENGINE", encoding="utf-8")
    (repo / "templates").mkdir(parents=True)
    (repo / "templates" / "PROMPT.md").write_text("NEW TEMPLATE PROMPT", encoding="utf-8")
    return repo


def _fake_live(tmp_path: Path) -> Path:
    live = tmp_path / "live"
    (live / "engine").mkdir(parents=True)
    (live / "engine" / "run.py").write_text("OLD ENGINE", encoding="utf-8")
    (live / "templates").mkdir(parents=True)
    (live / "templates" / "PROMPT.md").write_text("OLD TEMPLATE", encoding="utf-8")
    (live / "projects" / "acme").mkdir(parents=True)
    (live / "projects" / "acme" / "PROMPT.md").write_text("FROZEN OLD PROMPT", encoding="utf-8")
    return live


def test_dry_run_changes_nothing(tmp_path):
    repo, live = _fake_repo(tmp_path), _fake_live(tmp_path)
    dtl.deploy(repo, live, apply=False, refresh_projects=True, stamp="TS")
    assert (live / "engine" / "run.py").read_text() == "OLD ENGINE"   # untouched
    assert (live / "templates" / "PROMPT.md").read_text() == "OLD TEMPLATE"
    assert (live / "projects" / "acme" / "PROMPT.md").read_text() == "FROZEN OLD PROMPT"
    assert not (live / "engine.backup-TS").exists()


def test_apply_syncs_backs_up_and_refreshes_tenant_prompt(tmp_path):
    repo, live = _fake_repo(tmp_path), _fake_live(tmp_path)
    summary = dtl.deploy(repo, live, apply=True, refresh_projects=True, stamp="TS")

    # engine + templates synced from repo
    assert (live / "engine" / "run.py").read_text() == "NEW ENGINE"
    assert (live / "templates" / "PROMPT.md").read_text() == "NEW TEMPLATE PROMPT"
    # backups kept (never destroy the old state)
    assert (live / "engine.backup-TS" / "run.py").read_text() == "OLD ENGINE"
    assert (live / "templates.backup-TS" / "PROMPT.md").read_text() == "OLD TEMPLATE"
    # frozen tenant prompt force-refreshed, old copy preserved
    assert (live / "projects" / "acme" / "PROMPT.md").read_text() == "NEW TEMPLATE PROMPT"
    assert (live / "projects" / "acme" / "PROMPT.md.backup-TS").read_text() == "FROZEN OLD PROMPT"
    assert summary["prompts_refreshed"] == ["acme"]


def test_skip_projects_leaves_tenant_prompts(tmp_path):
    repo, live = _fake_repo(tmp_path), _fake_live(tmp_path)
    dtl.deploy(repo, live, apply=True, refresh_projects=False, stamp="TS")
    assert (live / "projects" / "acme" / "PROMPT.md").read_text() == "FROZEN OLD PROMPT"


def test_missing_repo_dirs_raises(tmp_path):
    live = _fake_live(tmp_path)
    with pytest.raises(FileNotFoundError):
        dtl.deploy(tmp_path / "nope", live, apply=False, refresh_projects=True, stamp="TS")
