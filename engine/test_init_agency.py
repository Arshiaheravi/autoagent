#!/usr/bin/env python3
"""Unit tests for init_agency.py — init(), _sync_dir(), shell wrapper."""
import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

import init_agency


# ---------------------------------------------------------------------------
# init() — directory creation
# ---------------------------------------------------------------------------

def test_init_creates_all_directories(tmp_path):
    """init() creates the expected subdirectory structure."""
    home = tmp_path / "agency"
    home.mkdir()
    with patch.object(init_agency, "REPO_ROOT", tmp_path / "fake_repo"):
        init_agency.init(home)

    expected = [
        "engine", "templates/agents", "templates/meta",
        "templates/examples", "skills", "projects", "dashboard",
    ]
    for d in expected:
        assert (home / d).is_dir(), f"Missing directory: {d}"


# ---------------------------------------------------------------------------
# init() — agency.json
# ---------------------------------------------------------------------------

def test_init_creates_agency_json(tmp_path):
    """init() creates agency.json with default contents when it doesn't exist."""
    home = tmp_path / "agency"
    home.mkdir()
    with patch.object(init_agency, "REPO_ROOT", tmp_path / "fake_repo"):
        init_agency.init(home)

    agency_file = home / "agency.json"
    assert agency_file.exists()
    data = json.loads(agency_file.read_text())
    assert data["projects"] == {}
    assert "model" in data["defaults"]


def test_init_preserves_existing_agency_json(tmp_path):
    """init() does NOT overwrite an existing agency.json."""
    home = tmp_path / "agency"
    home.mkdir()
    agency_file = home / "agency.json"
    original = {"projects": {"myproj": {}}, "custom": True}
    agency_file.write_text(json.dumps(original))

    with patch.object(init_agency, "REPO_ROOT", tmp_path / "fake_repo"):
        init_agency.init(home)

    data = json.loads(agency_file.read_text())
    assert data == original


# ---------------------------------------------------------------------------
# init() — engine file copying
# ---------------------------------------------------------------------------

def test_init_copies_engine_files_excludes_tests(tmp_path):
    """init() copies runtime .py files recursively but skips test files."""
    home = tmp_path / "agency"
    home.mkdir()

    # Create a fake repo with engine dir
    fake_repo = tmp_path / "fake_repo"
    engine_src = fake_repo / "engine"
    engine_src.mkdir(parents=True)
    (engine_src / "cli.py").write_text("# cli")
    (engine_src / "run.py").write_text("# run")
    (engine_src / "council.py").write_text("# stale module")
    (engine_src / "test_cli.py").write_text("# test")
    (engine_src / "conftest.py").write_text("# pytest")
    package = engine_src / "council"
    package.mkdir()
    (package / "__init__.py").write_text("# package")
    (package / "backends.py").write_text("# backends")
    (package / "test_backends.py").write_text("# test")

    with patch.object(init_agency, "REPO_ROOT", fake_repo):
        init_agency.init(home)

    assert (home / "engine" / "cli.py").exists()
    assert (home / "engine" / "run.py").exists()
    assert (home / "engine" / "council" / "__init__.py").exists()
    assert (home / "engine" / "council" / "backends.py").exists()
    assert not (home / "engine" / "council.py").exists()
    assert not (home / "engine" / "test_cli.py").exists()
    assert not (home / "engine" / "conftest.py").exists()
    assert not (home / "engine" / "council" / "test_backends.py").exists()


def test_init_removes_stale_module_when_package_exists(tmp_path):
    """init() removes old module files that conflict with deployed packages."""
    home = tmp_path / "agency"
    home.mkdir()
    stale = home / "engine" / "council.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("# old council")

    fake_repo = tmp_path / "fake_repo"
    package = fake_repo / "engine" / "council"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# new council")

    with patch.object(init_agency, "REPO_ROOT", fake_repo):
        init_agency.init(home)

    assert not stale.exists()
    assert (home / "engine" / "council" / "__init__.py").exists()


# ---------------------------------------------------------------------------
# init() — shell wrapper
# ---------------------------------------------------------------------------

def test_init_creates_shell_wrapper(tmp_path):
    """init() creates an executable shell wrapper script."""
    home = tmp_path / "agency"
    home.mkdir()
    with patch.object(init_agency, "REPO_ROOT", tmp_path / "fake_repo"):
        init_agency.init(home)

    wrapper = home / "autoagent"
    assert wrapper.exists()
    content = wrapper.read_text()
    assert "#!/bin/bash" in content
    assert "cli.py" in content
    # Check executable permission
    mode = wrapper.stat().st_mode
    assert mode & stat.S_IXUSR


# ---------------------------------------------------------------------------
# _sync_dir — copies new files, skips existing
# ---------------------------------------------------------------------------

def test_sync_dir_copies_new_files(tmp_path):
    """_sync_dir copies files from src to dst, creating subdirs."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("alpha")
    sub = src / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("beta")

    dst = tmp_path / "dst"
    dst.mkdir()

    init_agency._sync_dir(src, dst)

    assert (dst / "a.md").read_text() == "alpha"
    assert (dst / "sub" / "b.md").read_text() == "beta"


def test_sync_dir_no_overwrite(tmp_path):
    """_sync_dir does NOT overwrite existing files in dst."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("new content")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "a.md").write_text("original content")

    init_agency._sync_dir(src, dst)

    assert (dst / "a.md").read_text() == "original content"


def test_sync_dir_missing_src(tmp_path):
    """_sync_dir gracefully handles a missing src directory."""
    dst = tmp_path / "dst"
    dst.mkdir()

    # Should not raise
    init_agency._sync_dir(tmp_path / "nonexistent", dst)
    # dst should be untouched
    assert list(dst.iterdir()) == []
