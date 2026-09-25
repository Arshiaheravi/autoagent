"""Shared test fixtures — isolates AGENCY_HOME per-test so no cross-contamination."""
import sys
from pathlib import Path

import pytest

# Support `pytest` run from repo root OR from engine/. Add engine/ to sys.path
# when bare imports would otherwise fail.
_ENGINE_DIR = Path(__file__).parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

import registry  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_agency_home(tmp_path, monkeypatch):
    """Every test gets its own AGENCY_HOME. monkeypatch auto-reverts after each test."""
    home = tmp_path / "agency_home"
    home.mkdir()

    # Patch the module-level global
    monkeypatch.setattr(registry, "AGENCY_HOME", home)
    monkeypatch.setenv("AUTOAGENT_HOME", str(home))

    # Patch local bindings in modules that do `from registry import AGENCY_HOME`
    import intake
    monkeypatch.setattr(intake, "AGENCY_HOME", home)
    try:
        import orchestrator
        monkeypatch.setattr(orchestrator, "AGENCY_HOME", home)
    except (ImportError, AttributeError):
        pass

    # self_improve computes AGENCY_LOCK = AGENCY_HOME/".agency.lock" at IMPORT
    # time, so patching registry.AGENCY_HOME above doesn't reach it. Isolate the
    # lock per-test too — otherwise cmd_run's PID lock (released only at process
    # exit via atexit) leaks across tests: the first cmd_run test writes pytest's
    # live PID, and a later cmd_run test sees a "held" lock and bails.
    try:
        import self_improve
        monkeypatch.setattr(self_improve, "AGENCY_LOCK", home / ".agency.lock")
    except (ImportError, AttributeError):
        pass

    # Create minimal directory skeleton
    for d in ["projects", "skills", "templates/agents", "templates/meta"]:
        (home / d).mkdir(parents=True, exist_ok=True)

    yield home
