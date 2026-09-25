"""Tests for dream.py — DREAM mode creative synthesis."""
import json
from datetime import date
from pathlib import Path

import dream


def _make_sessions(tmp_path: Path, projects: dict) -> dict:
    """Create project dirs with sessions.json files. Returns {name: sessions_file}."""
    result = {}
    for name, sessions in projects.items():
        d = tmp_path / name
        d.mkdir()
        sf = d / "sessions.json"
        sf.write_text(json.dumps(sessions))
        result[name] = sf
    return result


# ── generate_dream_ideas ─────────────────────────────────────


def test_dream_generates_cross_project_ideas(tmp_path):
    """Core test: when two projects have complementary data, DREAM generates connection ideas."""
    today = date.today().isoformat()
    files = _make_sessions(tmp_path, {
        "cultivOS": [
            {"session": 1, "date": today, "type": "work",
             "summary": "Added weather data pipeline for farm microclimate tracking"},
        ],
        "StockCards": [
            {"session": 1, "date": today, "type": "work",
             "summary": "Added market regime detection from price volatility patterns"},
        ],
    })
    ideas = dream.generate_dream_ideas(files)
    assert len(ideas) >= 1
    for idea in ideas:
        assert "idea" in idea
        assert idea["confidence"] in ("low", "medium", "high")
        assert idea["effort"] in ("small", "medium", "large")
        assert "date" in idea
        assert "projects" in idea
        assert len(idea["projects"]) >= 2  # cross-project


def test_dream_no_ideas_single_project(tmp_path):
    """With only one project, no cross-project ideas are possible."""
    today = date.today().isoformat()
    files = _make_sessions(tmp_path, {
        "solo": [
            {"session": 1, "date": today, "type": "work",
             "summary": "Built login page"},
        ],
    })
    ideas = dream.generate_dream_ideas(files)
    assert ideas == []


def test_dream_filters_old_sessions(tmp_path):
    """Sessions older than 24h are excluded from dream synthesis."""
    files = _make_sessions(tmp_path, {
        "A": [
            {"session": 1, "date": "2020-01-01", "type": "work",
             "summary": "Ancient weather pipeline"},
        ],
        "B": [
            {"session": 1, "date": "2020-01-01", "type": "work",
             "summary": "Ancient market data"},
        ],
    })
    ideas = dream.generate_dream_ideas(files)
    assert ideas == []


def test_dream_empty_sessions(tmp_path):
    """Empty sessions files produce no ideas."""
    files = _make_sessions(tmp_path, {
        "A": [],
        "B": [],
    })
    ideas = dream.generate_dream_ideas(files)
    assert ideas == []


def test_dream_missing_sessions_file(tmp_path):
    """Missing sessions file is handled gracefully."""
    files = {"ghost": tmp_path / "nonexistent" / "sessions.json"}
    ideas = dream.generate_dream_ideas(files)
    assert ideas == []


def test_dream_writes_to_dreams_md(tmp_path):
    """write_dreams() persists ideas to a markdown file."""
    ideas = [
        {"idea": "What if weather → market correlation?", "confidence": "high",
         "effort": "medium", "date": "2026-04-03",
         "projects": ["cultivOS", "StockCards"]},
    ]
    out = tmp_path / "dreams.md"
    dream.write_dreams(ideas, out)
    content = out.read_text()
    assert "weather" in content.lower()
    assert "cultivOS" in content
    assert "PURSUE" in content or "RUMINATE" in content or "Filtered" in content


def test_dream_appends_to_existing_dreams(tmp_path):
    """write_dreams() appends, does not overwrite existing content."""
    out = tmp_path / "dreams.md"
    out.write_text("# Dreams\n\n## 2026-04-01\n- Old idea\n")
    ideas = [
        {"idea": "New idea", "confidence": "medium", "effort": "small",
         "date": "2026-04-03", "projects": ["A", "B"]},
    ]
    dream.write_dreams(ideas, out)
    content = out.read_text()
    assert "Old idea" in content
    assert "New idea" in content
