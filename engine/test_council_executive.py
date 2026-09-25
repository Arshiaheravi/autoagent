"""Unit tests for council.executive — pipeline stages, debate, task picking."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import council.executive as ce
import council.personas


# ── _build_executive_review_prompt ─────────────────────────────────

def test_build_prompt_includes_question():
    p = ce._build_executive_review_prompt("should we ship?", "", "a strategist")
    assert "should we ship?" in p
    assert "a strategist" in p


def test_build_prompt_includes_context_when_provided():
    p = ce._build_executive_review_prompt("q", "diff here", "brief")
    assert "diff here" in p
    assert "Context:" in p


def test_build_prompt_omits_context_when_empty():
    p = ce._build_executive_review_prompt("q", "", "brief")
    assert "Context:" not in p


# ── _collect_from_specs ────────────────────────────────────────────

def test_collect_from_specs_executive_mode():
    specs = {
        "claude": {"name": "Claude", "backend": "claude", "brief": "strategist"},
        "codex": {"name": "Codex", "backend": "openai", "brief": "operator"},
    }
    with patch.object(ce, "_call_claude", return_value="claude says"), \
         patch.object(ce, "_call_codex", return_value="codex says"):
        results = ce._collect_from_specs("question", "ctx", specs, mode="executive")
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert "Claude" in names and "Codex" in names


def test_collect_from_specs_personas_mode():
    specs = {
        "bull": {"name": "The Bull", "backend": "claude", "prompt": "be bullish"},
    }
    with patch.object(ce, "_call_claude", return_value="bull response"):
        results = ce._collect_from_specs("question", "", specs, mode="personas")
    assert len(results) == 1
    assert results[0]["persona"] == "bull"
    assert results[0]["response"] == "bull response"


def test_collect_from_specs_skips_empty_responses():
    specs = {
        "a": {"name": "A", "backend": "claude", "brief": "x"},
        "b": {"name": "B", "backend": "openai", "brief": "y"},
    }
    with patch.object(ce, "_call_claude", return_value="ok"), \
         patch.object(ce, "_call_codex", return_value=""):
        results = ce._collect_from_specs("q", "", specs, mode="executive")
    assert len(results) == 1
    assert results[0]["name"] == "A"


# ── _stage1_collect — mode routing ─────────────────────────────────

def test_stage1_executive_uses_executive_reviewers():
    with patch.object(ce, "_collect_from_specs", return_value=[]) as mock:
        ce._stage1_collect("q", mode="executive")
    mock.assert_called_once()
    args = mock.call_args
    assert args[0][2] == council.personas.EXECUTIVE_REVIEWERS
    assert args[1]["mode"] == "executive"


def test_stage1_personas_uses_personas():
    with patch.object(ce, "_collect_from_specs", return_value=[]) as mock:
        ce._stage1_collect("q", mode="personas")
    mock.assert_called_once()
    args = mock.call_args
    assert args[0][2] == council.personas.PERSONAS
    assert args[1]["mode"] == "personas"


# ── _stage2_rank ───────────────────────────────────────────────────

def test_stage2_rank_calls_fallback_per_result():
    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    with patch.object(ce, "_call_with_fallback",
                      return_value="FINAL RANKING: Response A, Response B."):
        result = ce._stage2_rank("question", stage1)
    assert "rankings" in result
    assert "aggregate" in result
    assert len(result["rankings"]) == 2


def test_stage2_rank_label_map_correct():
    stage1 = [
        {"persona": "x", "name": "X", "response": "r1"},
        {"persona": "y", "name": "Y", "response": "r2"},
        {"persona": "z", "name": "Z", "response": "r3"},
    ]
    with patch.object(ce, "_call_with_fallback",
                      return_value="FINAL RANKING: Response A, Response B, Response C."):
        result = ce._stage2_rank("q", stage1)
    assert result["label_map"] == {"A": "X", "B": "Y", "C": "Z"}


# ── _stage3_synthesize ─────────────────────────────────────────────

def test_stage3_uses_advisor_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    stage1 = [{"name": "A", "response": "x"}]
    stage2 = {"aggregate": [{"name": "A", "avg_position": 1}]}
    import advisor as adv_mod
    with patch.object(adv_mod, "advise", return_value="advisor synthesis"):
        result = ce._stage3_synthesize("q", stage1, stage2)
    assert result == "advisor synthesis"


def test_stage3_falls_back_when_advisor_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    stage1 = [{"name": "A", "response": "x"}]
    stage2 = {"aggregate": [{"name": "A", "avg_position": 1}]}
    import advisor as adv_mod
    with patch.object(adv_mod, "advise", return_value=""), \
         patch.object(ce, "_call_with_fallback", return_value="fallback"):
        result = ce._stage3_synthesize("q", stage1, stage2)
    assert result == "fallback"


def test_stage3_falls_back_when_advisor_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    stage1 = [{"name": "A", "response": "x"}]
    stage2 = {"aggregate": [{"name": "A", "avg_position": 1}]}
    import advisor as adv_mod
    with patch.object(adv_mod, "advise", side_effect=Exception("boom")), \
         patch.object(ce, "_call_with_fallback", return_value="safe"):
        result = ce._stage3_synthesize("q", stage1, stage2)
    assert result == "safe"


def test_stage3_no_api_key_skips_advisor(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    stage1 = [{"name": "A", "response": "x"}]
    stage2 = {"aggregate": [{"name": "A", "avg_position": 1}]}
    with patch.object(ce, "_call_with_fallback", return_value="direct"):
        result = ce._stage3_synthesize("q", stage1, stage2)
    assert result == "direct"


def test_stage3_custom_chairman_prompt(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    stage1 = [{"name": "A", "response": "x"}]
    stage2 = {"aggregate": [{"name": "A", "avg_position": 1}]}
    prompts_seen = []

    def capture(prompt, backends, timeout):
        prompts_seen.append(prompt)
        return "result"

    with patch.object(ce, "_call_with_fallback", side_effect=capture):
        ce._stage3_synthesize("q", stage1, stage2, chairman_prompt="Custom chair")
    assert "Custom chair" in prompts_seen[0]


# ── convene_council_with_debate ────────────────────────────────────

def test_debate_converges_on_high_confidence():
    high_result = {
        "question": "q", "confidence": "HIGH",
        "synthesis": "agreed. HIGH", "stage1": [],
        "stage2": {"aggregate": [{"name": "A", "avg_position": 1}]},
        "winner": "A",
    }
    with patch.object(ce, "convene_council", return_value=high_result):
        result = ce.convene_council_with_debate("q")
    assert result["status"] == "converged"
    assert len(result["rounds"]) == 1


def test_debate_benches_when_never_converges(tmp_path):
    low_result = {
        "question": "q", "confidence": "LOW",
        "synthesis": "disagree. LOW", "stage1": [
            {"name": "A", "response": "r1", "backend": "claude"},
        ],
        "stage2": {"aggregate": [{"name": "A", "avg_position": 1}]},
        "winner": "A",
    }
    with patch.object(ce, "convene_council", return_value=low_result):
        result = ce.convene_council_with_debate("q", max_rounds=2,
                                                 bench_dir=tmp_path, task_id="T1")
    assert result["status"] == "benched"
    assert len(result["rounds"]) == 2
    bench_files = list(tmp_path.glob("*.md"))
    assert len(bench_files) == 1
    content = bench_files[0].read_text()
    assert "BENCHED" in content
    assert "T1" in content


def test_debate_stops_if_synthesis_empty():
    empty_result = {
        "question": "q", "confidence": "MEDIUM",
        "synthesis": "", "stage1": [],
        "stage2": {"aggregate": []},
        "winner": "Unknown",
    }
    with patch.object(ce, "convene_council", return_value=empty_result):
        result = ce.convene_council_with_debate("q", max_rounds=5)
    assert len(result["rounds"]) == 1


# ── council_pick_task ──────────────────────────────────────────────

def test_pick_task_returns_none_fewer_than_3():
    tasks = [{"id": "t1", "name": "A"}, {"id": "t2", "name": "B"}]
    assert ce.council_pick_task("proj", tasks) is None


def test_pick_task_returns_matching_id():
    tasks = [
        {"id": "t1", "name": "Build API"},
        {"id": "t2", "name": "Fix bug"},
        {"id": "t3", "name": "Write docs"},
    ]
    result = {"synthesis": "The team should focus on t2 for maximum impact."}
    with patch.object(ce, "convene_council", return_value=result):
        picked = ce.council_pick_task("proj", tasks, north_star="ship fast")
    assert picked == "t2"


def test_pick_task_returns_none_no_match():
    tasks = [
        {"id": "t1", "name": "Build API"},
        {"id": "t2", "name": "Fix bug"},
        {"id": "t3", "name": "Write docs"},
    ]
    result = {"synthesis": "None of the tasks seem relevant."}
    with patch.object(ce, "convene_council", return_value=result):
        picked = ce.council_pick_task("proj", tasks)
    assert picked is None


def test_pick_task_matches_by_name_prefix():
    tasks = [
        {"id": "t1", "name": "Build the authentication system"},
        {"id": "t2", "name": "Fix database migration"},
        {"id": "t3", "name": "Write API documentation"},
    ]
    result = {"synthesis": "Build the authentication syste is highest priority."}
    with patch.object(ce, "convene_council", return_value=result):
        picked = ce.council_pick_task("proj", tasks)
    assert picked == "t1"


# ── convene_council confidence extraction ──────────────────────────

def test_convene_council_extracts_low_confidence():
    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [
        {"label": "A", "name": "A", "avg_position": 1, "positions": [1]},
    ]}
    with patch.object(ce, "_stage1_collect", return_value=stage1), \
         patch.object(ce, "_stage2_rank", return_value=stage2), \
         patch.object(ce, "_stage3_synthesize", return_value="risky move. Confidence: LOW"):
        result = ce.convene_council("q")
    assert result["confidence"] == "LOW"


def test_convene_council_includes_decision_id():
    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [
        {"label": "A", "name": "A", "avg_position": 1, "positions": [1]},
    ]}
    with patch.object(ce, "_stage1_collect", return_value=stage1), \
         patch.object(ce, "_stage2_rank", return_value=stage2), \
         patch.object(ce, "_stage3_synthesize", return_value="ok. HIGH"), \
         patch("council.executive.log_council_decision", return_value=42, create=True):
        result = ce.convene_council("q")
    assert "decision_id" in result


def test_convene_council_mode_field_in_result():
    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [
        {"label": "A", "name": "A", "avg_position": 1, "positions": [1]},
    ]}
    with patch.object(ce, "_stage1_collect", return_value=stage1), \
         patch.object(ce, "_stage2_rank", return_value=stage2), \
         patch.object(ce, "_stage3_synthesize", return_value="ok. MEDIUM"):
        result = ce.convene_council("q", mode="personas")
    assert result["mode"] == "personas"
