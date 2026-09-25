"""Unit tests for council package — covers fall-through and branching logic.

After the council.py → council/ package split, patches target the submodule
where each function lives:
    council.backends  — model callers, _find_claude, _call_with_fallback
    council.executive — 3-stage pipeline, convene_council, reviews
    council.personas  — PERSONAS dict, CHAIRMAN_PROMPT, etc.
"""

import os
from unittest.mock import patch, MagicMock

import council
import council.backends
import council.executive
import council.personas


# ── _find_claude ─────────────────────────────────────────────────────

def test_find_claude_returns_which_result():
    with patch("council.backends.shutil.which", return_value="/usr/local/bin/claude"):
        assert council._find_claude() == "/usr/local/bin/claude"


def test_find_claude_falls_back_to_bare_name():
    with patch("council.backends.shutil.which", return_value=None):
        assert council._find_claude() == "claude"


# ── Backend callers — missing-key fall-through ───────────────────────

def test_call_codex_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert council._call_codex("anything") == ""


def test_call_gemini_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert council._call_gemini("anything") == ""


def test_call_deepseek_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert council._call_deepseek("anything") == ""


def test_call_grok_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert council._call_grok("anything") == ""


# ── _call_claude subprocess handling ─────────────────────────────────

def test_call_claude_returns_stdout_on_success():
    fake = MagicMock(returncode=0, stdout="hello world\n")
    with patch("council.backends.subprocess.run", return_value=fake):
        assert council._call_claude("q") == "hello world"


def test_call_claude_returns_empty_on_nonzero_returncode():
    fake = MagicMock(returncode=1, stdout="anything")
    with patch("council.backends.subprocess.run", return_value=fake):
        assert council._call_claude("q") == ""


def test_call_claude_returns_empty_on_timeout():
    import subprocess
    with patch("council.backends.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)):
        assert council._call_claude("q", timeout=1) == ""


# ── _call_with_fallback walk-through ─────────────────────────────────

def test_fallback_returns_first_nonempty_backend():
    calls = []

    def ok(prompt, timeout=120):
        calls.append("claude")
        return "OK"

    with patch.object(council.backends, "_call_claude", side_effect=ok), \
         patch.object(council.backends, "_call_codex", return_value=""):
        out = council._call_with_fallback("q", backends=("claude", "openai"))
    assert out == "OK"
    assert calls == ["claude"]


def test_fallback_walks_until_hit():
    with patch.object(council.backends, "_call_claude", return_value=""), \
         patch.object(council.backends, "_call_codex", return_value=""), \
         patch.object(council.backends, "_call_gemini", return_value="gem"):
        out = council._call_with_fallback("q", backends=("claude", "openai", "gemini"))
    assert out == "gem"


def test_fallback_returns_empty_when_all_fail():
    with patch.object(council.backends, "_call_claude", return_value=""), \
         patch.object(council.backends, "_call_codex", return_value=""), \
         patch.object(council.backends, "_call_gemini", return_value=""), \
         patch.object(council.backends, "_call_deepseek", return_value=""):
        out = council._call_with_fallback(
            "q", backends=("claude", "openai", "gemini", "deepseek")
        )
    assert out == ""


def test_fallback_skips_unknown_backend():
    with patch.object(council.backends, "_call_claude", return_value="OK"):
        out = council._call_with_fallback("q", backends=("bogus", "claude"))
    assert out == "OK"


# ── _parse_ranking ───────────────────────────────────────────────────

def test_parse_ranking_structured_final_ranking_block():
    text = "Here is my ranking.\nFINAL RANKING: Response B, Response A, Response C."
    assert council._parse_ranking(text, ["A", "B", "C"]) == ["B", "A", "C"]


def test_parse_ranking_fallback_inline_mentions():
    text = "I prefer Response C over Response A with Response B last."
    out = council._parse_ranking(text, ["A", "B", "C"])
    assert out == ["C", "A", "B"]


def test_parse_ranking_returns_labels_when_no_parse_possible():
    text = "I cannot rank these."
    assert council._parse_ranking(text, ["A", "B", "C"]) == ["A", "B", "C"]


def test_parse_ranking_case_insensitive_and_dedupes():
    text = "response a is best. Response A stands out. Response b comes next."
    out = council._parse_ranking(text, ["A", "B", "C"])
    assert out[0] == "A"
    assert "A" in out and "B" in out


# ── _aggregate_rankings ──────────────────────────────────────────────

def test_aggregate_rankings_orders_by_mean_position():
    rankings = [
        {"parsed_ranking": ["A", "B", "C"]},
        {"parsed_ranking": ["B", "A", "C"]},
        {"parsed_ranking": ["A", "B", "C"]},
    ]
    label_map = {"A": "Alpha", "B": "Beta", "C": "Gamma"}
    out = council._aggregate_rankings(rankings, ["A", "B", "C"], label_map)
    names = [r["name"] for r in out]
    assert names[0] == "Alpha"
    assert names[-1] == "Gamma"


def test_aggregate_rankings_handles_missing_positions():
    rankings = [{"parsed_ranking": ["A"]}]  # B missing
    out = council._aggregate_rankings(rankings, ["A", "B"], {"A": "Alpha", "B": "Beta"})
    by_label = {r["label"]: r for r in out}
    assert by_label["A"]["avg_position"] == 1.0
    assert by_label["B"]["avg_position"] == 99


# ── convene_council — branching ──────────────────────────────────────

def test_convene_council_errors_when_not_enough_responses():
    def single_response(*args, **kwargs):
        return [{"persona": "bull", "name": "The Bull", "response": "only one"}]

    with patch.object(council.executive, "_stage1_collect", side_effect=single_response):
        result = council.convene_council("ship it?")
    assert "error" in result
    assert result["question"] == "ship it?"


def test_convene_council_happy_path_extracts_confidence():
    stage1 = [
        {"persona": "bull",  "name": "The Bull",  "response": "go"},
        {"persona": "bear",  "name": "The Bear",  "response": "wait"},
        {"persona": "codex", "name": "Codex",     "response": "neutral"},
    ]
    stage2 = {
        "rankings": [],
        "aggregate": [
            {"label": "A", "name": "The Bull", "avg_position": 1.2, "positions": [1, 2]},
            {"label": "B", "name": "The Bear", "avg_position": 1.8, "positions": [2, 1]},
        ],
    }
    synthesis = "Ship it. Overall confidence: HIGH"

    with patch.object(council.executive, "_stage1_collect", return_value=stage1), \
         patch.object(council.executive, "_stage2_rank", return_value=stage2), \
         patch.object(council.executive, "_stage3_synthesize", return_value=synthesis):
        result = council.convene_council("ship it?", context="diff here")

    assert result["confidence"] == "HIGH"
    assert result["winner"] == "The Bull"
    assert result["synthesis"] == synthesis


def test_convene_council_uses_advisor_path_when_api_key_set(monkeypatch):
    """Chairman synthesis routes through engine/advisor.py when ANTHROPIC_API_KEY is present."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [{"label": "A", "name": "A", "avg_position": 1, "positions": [1]}]}

    import advisor as _advisor_mod
    with patch.object(_advisor_mod, "advise", return_value="advisor-path synthesis. Confidence: HIGH") as mock_advise:
        with patch.object(council.executive, "_stage1_collect", return_value=stage1), \
             patch.object(council.executive, "_stage2_rank", return_value=stage2):
            result = council.convene_council("q")
    assert mock_advise.called
    assert result["synthesis"] == "advisor-path synthesis. Confidence: HIGH"
    assert result["confidence"] == "HIGH"


def test_convene_council_falls_back_when_advisor_returns_empty(monkeypatch):
    """If advisor.advise returns '', legacy _call_with_fallback takes over."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [{"label": "A", "name": "A", "avg_position": 1, "positions": [1]}]}

    import advisor as _advisor_mod
    with patch.object(_advisor_mod, "advise", return_value=""), \
         patch.object(council.executive, "_call_with_fallback", return_value="legacy synthesis. MEDIUM"):
        with patch.object(council.executive, "_stage1_collect", return_value=stage1), \
             patch.object(council.executive, "_stage2_rank", return_value=stage2):
            result = council.convene_council("q")
    assert result["synthesis"] == "legacy synthesis. MEDIUM"


def test_convene_council_skips_advisor_without_api_key(monkeypatch):
    """No ANTHROPIC_API_KEY → legacy chain runs directly, advisor never called."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [{"label": "A", "name": "A", "avg_position": 1, "positions": [1]}]}

    import advisor as _advisor_mod
    with patch.object(_advisor_mod, "advise") as mock_advise, \
         patch.object(council.executive, "_call_with_fallback", return_value="legacy-only. LOW"):
        with patch.object(council.executive, "_stage1_collect", return_value=stage1), \
             patch.object(council.executive, "_stage2_rank", return_value=stage2):
            result = council.convene_council("q")
    assert not mock_advise.called
    assert result["synthesis"] == "legacy-only. LOW"


def test_convene_council_defaults_confidence_medium_when_missing():
    stage1 = [
        {"persona": "a", "name": "A", "response": "x"},
        {"persona": "b", "name": "B", "response": "y"},
    ]
    stage2 = {"rankings": [], "aggregate": [{"label": "A", "name": "A", "avg_position": 1, "positions": [1]}]}
    synthesis = "Answer without a confidence tag at all."

    with patch.object(council.executive, "_stage1_collect", return_value=stage1), \
         patch.object(council.executive, "_stage2_rank", return_value=stage2), \
         patch.object(council.executive, "_stage3_synthesize", return_value=synthesis):
        result = council.convene_council("q")
    assert result["confidence"] == "MEDIUM"


# ── Module-split smoke tests ────────────────────────────────────────

def test_smoke_backends_exports_callers():
    from council.backends import (
        _call_claude, _call_codex, _call_gemini, _call_deepseek, _call_grok,
        _call_with_fallback, _find_claude,
    )
    assert callable(_call_claude)
    assert callable(_call_with_fallback)
    assert callable(_find_claude)


def test_smoke_backends_find_claude_returns_string():
    result = council.backends._find_claude()
    assert isinstance(result, str)
    assert len(result) > 0


def test_smoke_backends_vision_callers_exist():
    from council.backends import _call_gemini_vision, _call_openai_vision
    assert callable(_call_gemini_vision)
    assert callable(_call_openai_vision)


def test_smoke_personas_has_expected_keys():
    from council.personas import PERSONAS, EXECUTIVE_REVIEWERS
    assert "bull" in PERSONAS
    assert "bear" in PERSONAS
    assert "ux" in PERSONAS
    assert "claude" in EXECUTIVE_REVIEWERS
    assert "gemini" in EXECUTIVE_REVIEWERS
    assert "grok" in EXECUTIVE_REVIEWERS


def test_smoke_personas_chairman_prompt_nonempty():
    from council.personas import CHAIRMAN_PROMPT
    assert isinstance(CHAIRMAN_PROMPT, str)
    assert len(CHAIRMAN_PROMPT) > 50


def test_smoke_personas_design_review_prompt_exists():
    from council.personas import DESIGN_REVIEW_PROMPT
    assert "visual hierarchy" in DESIGN_REVIEW_PROMPT.lower()


def test_smoke_executive_convene_council_importable():
    from council.executive import convene_council
    assert callable(convene_council)


def test_smoke_executive_parse_ranking_works():
    from council.executive import _parse_ranking
    text = "FINAL RANKING: Response B, Response A, Response C."
    assert _parse_ranking(text, ["A", "B", "C"]) == ["B", "A", "C"]


def test_smoke_reviews_functions_importable():
    from council.reviews import codex_review, ux_review, design_council
    assert callable(codex_review)
    assert callable(ux_review)
    assert callable(design_council)
