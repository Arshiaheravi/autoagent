"""Tests for scripts/build_template_prompt.py — the tenant-template compiler."""
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

btp = pytest.importorskip("build_template_prompt")

_ROOT = Path(__file__).resolve().parent.parent


def test_strip_advisor_council_removes_both_blocks():
    text = (
        "## WORK\nkeep me\n"
        "## ADVISOR (Opus)\nadvisor.sh stuff\n\nmore advisor\n"
        "## COUNCIL (5-model)\ncouncil.sh stuff\n"
        "## EVERY SESSION\nkeep me too\n"
    )
    out = btp.strip_advisor_council(text)
    assert "keep me" in out and "keep me too" in out
    assert "advisor.sh" not in out
    assert "council.sh" not in out
    assert "## ADVISOR" not in out and "## COUNCIL" not in out


def test_genericize_strips_agency_specifics():
    text = "Run src/cultivos/api/x.py — cultivOS rule. Seb reviews it. import src.cultivos.models"
    out = btp.genericize(text)
    assert "cultivos" not in out.lower()
    assert "Seb" not in out
    assert "src/app/api/x.py" in out
    assert "the operator reviews" in out


def test_compile_has_all_sections_and_no_leaks():
    text = btp.compile_template(_ROOT, include_advisor_council=False)
    for label in ("RECOVERY", "WORK", "CONTEXT", "FAILURE", "VERIFICATION"):
        assert f"==== {label} ====" in text
    # Tenant-safe: no client name, no operator name, no advisor/council infra
    assert "cultivos" not in text.lower()
    assert "advisor.sh" not in text and "council.sh" not in text
    assert "\nSeb " not in text
    # Superset of the thin live template — should be substantially longer
    assert len(text.splitlines()) > 400


def test_compile_can_keep_advisor_council_when_requested():
    text = btp.compile_template(_ROOT, include_advisor_council=True)
    assert "advisor.sh" in text  # kept when explicitly requested
