"""Tests for retry.py — exponential backoff on rate-limit errors."""
import pytest
from retry import should_retry, save_last_error, read_last_error


class TestShouldRetry:
    """should_retry(exit_code, attempt, last_error) → (bool, wait_seconds)"""

    def test_retry_on_rate_limit(self):
        """Rate-limit error on first attempt → should retry with 30s wait."""
        do_retry, wait = should_retry(1, 0, "rate limit exceeded")
        assert do_retry is True
        assert wait == 30

    def test_retry_on_rate_limit_second_attempt(self):
        """Rate-limit on second attempt → 60s backoff."""
        do_retry, wait = should_retry(1, 1, "429 Too Many Requests")
        assert do_retry is True
        assert wait == 60

    def test_retry_on_rate_limit_third_attempt(self):
        """Rate-limit on third attempt → 120s backoff."""
        do_retry, wait = should_retry(1, 2, "rate_limit_error")
        assert do_retry is True
        assert wait == 120

    def test_no_retry_on_logic_failure(self):
        """Non-rate-limit error → should not retry."""
        do_retry, wait = should_retry(1, 0, "SyntaxError: invalid syntax")
        assert do_retry is False
        assert wait == 0

    def test_no_retry_on_success(self):
        """Exit code 0 → no retry needed."""
        do_retry, wait = should_retry(0, 0, "")
        assert do_retry is False
        assert wait == 0

    def test_max_attempts_gives_up(self):
        """After max attempts (3), stop retrying even on rate limit."""
        do_retry, wait = should_retry(1, 3, "rate limit exceeded")
        assert do_retry is False
        assert wait == 0

    def test_rate_limit_keyword_overloaded(self):
        """Various rate-limit phrasings should all trigger retry."""
        for error_msg in ["overloaded", "503 Service Unavailable", "capacity"]:
            do_retry, _ = should_retry(1, 0, error_msg)
            assert do_retry is True, f"Should retry on: {error_msg}"

    def test_retry_on_weekly_usage_limit_phrase(self):
        """Weekly plan exhaustion should be treated like a retryable/fallback-worthy limit."""
        do_retry, wait = should_retry(1, 0, "Opus weekly usage limit reached. Resets in 6 days.")
        assert do_retry is True
        assert wait == 30

    def test_retry_on_extra_usage_banner(self):
        """Claude Code's extra-usage exhaustion banner should also trigger retry/fallback."""
        do_retry, wait = should_retry(1, 0, "You're out of extra usage. Resets 4pm.")
        assert do_retry is True
        assert wait == 30

    def test_empty_error_no_retry(self):
        """Empty error string with non-zero exit → no retry (not a rate limit)."""
        do_retry, wait = should_retry(1, 0, "")
        assert do_retry is False
        assert wait == 0


class TestErrorPersistence:
    """save_last_error / read_last_error round-trip."""

    def test_save_and_read(self, tmp_path):
        save_last_error(tmp_path, ["line1", "rate limit exceeded"])
        result = read_last_error(tmp_path)
        assert "rate limit exceeded" in result

    def test_read_missing_returns_empty(self, tmp_path):
        assert read_last_error(tmp_path) == ""

    def test_save_truncates_long_errors(self, tmp_path):
        lines = [f"error line {i}" for i in range(200)]
        save_last_error(tmp_path, lines)
        result = read_last_error(tmp_path)
        assert len(result) <= 2000
