"""Tests for model_fallback.py detection helpers."""
from model_fallback import is_rate_limit_error


def test_is_rate_limit_error_matches_weekly_usage_limit():
    """Claude plan exhaustion messages should trigger fallback routing."""
    assert is_rate_limit_error("Claude Opus weekly usage limit reached. Try again later.")


def test_is_rate_limit_error_matches_extra_usage_banner():
    """Claude Code's extra-usage banner should trigger fallback routing."""
    assert is_rate_limit_error("You're out of extra usage. Resets 4pm (America/Toronto).")


def test_is_rate_limit_error_matches_credit_exhaustion():
    """Credit depletion should also be treated as a fallback-worthy limit."""
    assert is_rate_limit_error("Insufficient credits. Your credits are depleted.")


def test_is_rate_limit_error_ignores_logic_errors():
    """Regular code failures must not route to a different model."""
    assert not is_rate_limit_error("SyntaxError: invalid syntax in engine/run.py")
