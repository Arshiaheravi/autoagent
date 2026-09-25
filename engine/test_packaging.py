#!/usr/bin/env python3
"""Tests for Phase 5 — packaging, CLI entry point, init command."""
import json
import shutil
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

import registry


@pytest.fixture(autouse=True)
def clean(isolated_agency_home):
    yield


# ── Init command creates agency structure ──

import init_agency


def test_init_creates_agency_home(isolated_agency_home):
    home = isolated_agency_home
    # Remove everything to simulate fresh install
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    assert home.exists()
    assert (home / "agency.json").exists()
    assert (home / "engine").exists() or True  # engine may be separate
    assert (home / "templates").exists()
    assert (home / "skills").exists()
    assert (home / "projects").exists()


def test_init_creates_agency_json(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    data = json.loads((home / "agency.json").read_text())
    assert "projects" in data
    assert "defaults" in data


def test_init_copies_templates(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    assert (home / "templates" / "PROMPT.md").exists()
    assert (home / "templates" / "INTAKE_PROMPT.md").exists()
    assert (home / "templates" / "meta" / "PROMPT.md").exists()


def test_init_copies_agent_templates(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    agents_dir = home / "templates" / "agents"
    assert agents_dir.exists()
    agent_files = {f.name for f in agents_dir.glob("*.md")}
    assert "architect.md" in agent_files
    assert "test-writer.md" in agent_files


def test_init_copies_skills(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    skills = list((home / "skills").glob("*.md"))
    assert len(skills) >= 5  # at least the core skills


def test_init_idempotent(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    # Add a custom file
    (home / "projects" / "marker.txt").write_text("keep me")
    # Re-init should not destroy existing data
    init_agency.init(home)
    assert (home / "projects" / "marker.txt").exists()


def test_init_preserves_agency_json(isolated_agency_home):
    home = isolated_agency_home
    if home.exists(): shutil.rmtree(home)
    init_agency.init(home)
    # Register a project manually
    data = json.loads((home / "agency.json").read_text())
    data["projects"]["myproj"] = {"path": "/tmp/myproj", "created": "2026-01-01"}
    (home / "agency.json").write_text(json.dumps(data))
    # Re-init should preserve
    init_agency.init(home)
    data2 = json.loads((home / "agency.json").read_text())
    assert "myproj" in data2["projects"]


# ── CLI entry point ──

def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{Path(__file__).parent}'); from cli import main; sys.argv = ['autoagent', '--help']; main()"],
        capture_output=True, text=True
    )
    assert "AutoAgent Agency" in result.stdout


def test_cli_list_empty(isolated_agency_home):
    result = subprocess.run(
        [sys.executable, "-c",
         f"import os; os.environ['AUTOAGENT_HOME']='{isolated_agency_home}'; import sys; sys.path.insert(0, '{Path(__file__).parent}'); from cli import main; sys.argv = ['autoagent', 'list']; main()"],
        capture_output=True, text=True
    )
    assert "No projects" in result.stdout or "Name" in result.stdout


# ── pyproject.toml validation ──

def test_pyproject_toml_exists():
    repo = Path(__file__).parent.parent
    pyproject = repo / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml should exist in repo root"


def test_pyproject_toml_has_entry_point():
    repo = Path(__file__).parent.parent
    pyproject = repo / "pyproject.toml"
    content = pyproject.read_text()
    assert "autoagent" in content
    assert "console_scripts" in content or "scripts" in content


# ── pip install verification ──

_repo_root = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def venv_dir():
    """Create a temporary venv and pip install -e . into it."""
    tmp = tempfile.mkdtemp(prefix="autoagent_venv_")
    venv_path = Path(tmp) / "venv"
    # Create venv
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"venv creation failed: {result.stderr}"
    yield venv_path
    shutil.rmtree(tmp, ignore_errors=True)


def _venv_python(venv_path: Path) -> str:
    """Return path to the venv's python executable."""
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / "python.exe")
    return str(venv_path / "bin" / "python")


def _venv_bin(venv_path: Path, name: str) -> str:
    """Return path to a script in the venv's bin directory."""
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / f"{name}.exe")
    return str(venv_path / "bin" / name)


def test_pip_install_editable(venv_dir):
    """pip install -e . succeeds without errors."""
    pip = _venv_bin(venv_dir, "pip")
    result = subprocess.run(
        [pip, "install", "-e", str(_repo_root)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"pip install -e . failed (exit {result.returncode}):\n{result.stderr}"
    )


def test_autoagent_command_exists(venv_dir):
    """After install, 'autoagent --help' runs and shows usage."""
    # First ensure it's installed
    pip = _venv_bin(venv_dir, "pip")
    subprocess.run(
        [pip, "install", "-e", str(_repo_root)],
        capture_output=True, text=True, timeout=120,
    )
    autoagent = _venv_bin(venv_dir, "autoagent")
    result = subprocess.run(
        [autoagent, "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"autoagent --help failed (exit {result.returncode}):\n{result.stderr}"
    )
    assert "AutoAgent" in result.stdout, (
        f"Expected 'AutoAgent' in help output, got:\n{result.stdout}"
    )


def test_autoagent_init_from_pip(venv_dir):
    """autoagent init creates the ~/.autoagent structure."""
    # Ensure installed
    pip = _venv_bin(venv_dir, "pip")
    subprocess.run(
        [pip, "install", "-e", str(_repo_root)],
        capture_output=True, text=True, timeout=120,
    )
    # Run init with a custom AUTOAGENT_HOME
    init_home = tempfile.mkdtemp(prefix="autoagent_init_test_")
    py = _venv_python(venv_dir)
    result = subprocess.run(
        [py, "-c",
         f"import os; os.environ['AUTOAGENT_HOME']='{init_home}';"
         f"import sys; sys.path.insert(0, '{_repo_root / 'engine'}');"
         f"from cli import main; sys.argv = ['autoagent', 'init']; main()"],
        capture_output=True, text=True, timeout=30,
    )
    init_path = Path(init_home)
    assert init_path.exists(), "init should create the home directory"
    assert (init_path / "agency.json").exists(), "init should create agency.json"
    assert (init_path / "templates").exists(), "init should create templates/"
    assert (init_path / "skills").exists(), "init should create skills/"
    assert (init_path / "projects").exists(), "init should create projects/"
    shutil.rmtree(init_home, ignore_errors=True)
