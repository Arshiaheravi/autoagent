"""Tests for the model SSoT (engine/models.py)."""
import models


def test_default_model_is_current_opus():
    assert models.DEFAULT_MODEL == "claude-opus-4-8"


def test_work_defaults_to_sonnet_deliberation_to_opus():
    assert models.default_model_for_session("work") == "claude-sonnet-5"
    for t in ("meta", "brain", "deep", "audit"):
        assert models.default_model_for_session(t) == "claude-opus-4-8"


def test_unknown_session_type_falls_back_to_default():
    assert models.default_model_for_session("nonesuch") == models.DEFAULT_MODEL


def test_resolve_precedence_session_override_wins():
    cfg = {"model": "claude-opus-4-8", "models": {"work": "claude-haiku-4-5"}}
    assert models.resolve_model(cfg, "work") == "claude-haiku-4-5"


def test_resolve_falls_back_to_top_level_model():
    cfg = {"model": "claude-fable-5"}
    assert models.resolve_model(cfg, "work") == "claude-fable-5"


def test_resolve_falls_back_to_session_default_when_config_silent():
    assert models.resolve_model({}, "work") == "claude-sonnet-5"
    assert models.resolve_model(None, "brain") == "claude-opus-4-8"


def test_resolve_ignores_unrelated_session_override():
    cfg = {"models": {"meta": "claude-opus-4-8"}}  # no "work" key
    assert models.resolve_model(cfg, "work") == "claude-sonnet-5"


def test_default_daily_limit_is_ssot_value():
    # The budget gate / cost predictor / status readers all fall back to this
    # when a project.json omits daily_limit_usd — they must agree with intake.
    assert models.DEFAULT_DAILY_LIMIT_USD == 50.0
