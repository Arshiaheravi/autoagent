#!/usr/bin/env python3
"""Tests for test_gap_detector.py — auto-discover untested public functions."""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))


# ── Tests ─────────────────────────────────────────────────────

def test_detect_gaps_finds_untested(tmp_path):
    """Public functions without a matching test_* are flagged as untested."""
    from test_gap_detector import detect_test_gaps

    # Source file with 2 public functions
    src = tmp_path / "engine" / "my_module.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "def do_stuff():\n    pass\n\n"
        "def compute_score():\n    pass\n"
    )
    # Test file only covers do_stuff
    test = tmp_path / "engine" / "test_my_module.py"
    test.write_text(
        "def test_do_stuff():\n    pass\n"
    )

    gaps = detect_test_gaps([str(src)])
    assert len(gaps) == 1
    assert gaps[0]["function"] == "compute_score"
    assert gaps[0]["file"] == str(src)
    assert gaps[0]["has_test"] is False


def test_detect_gaps_ignores_private(tmp_path):
    """Functions starting with _ are not flagged as untested."""
    from test_gap_detector import detect_test_gaps

    src = tmp_path / "engine" / "helpers.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "def _internal_helper():\n    pass\n\n"
        "def __dunder_method():\n    pass\n\n"
        "def public_api():\n    pass\n"
    )
    test = tmp_path / "engine" / "test_helpers.py"
    test.write_text(
        "def test_public_api():\n    pass\n"
    )

    gaps = detect_test_gaps([str(src)])
    # Only public_api is public; it has a test, so no gaps
    assert len(gaps) == 0


def test_detect_gaps_empty_list_when_covered(tmp_path):
    """When all public functions have tests, return empty list."""
    from test_gap_detector import detect_test_gaps

    src = tmp_path / "engine" / "calc.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def subtract(a, b):\n    return a - b\n"
    )
    test = tmp_path / "engine" / "test_calc.py"
    test.write_text(
        "def test_add():\n    pass\n\n"
        "def test_subtract():\n    pass\n"
    )

    gaps = detect_test_gaps([str(src)])
    assert gaps == []
