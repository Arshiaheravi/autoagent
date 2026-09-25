"""Tests for context.py — JIT context loading, response truncation, context compaction."""

from context import load_jit, truncate_response, compact_context, estimate_tokens


def test_load_jit_by_path(tmp_path):
    """load_jit with a file path ref returns file content."""
    f = tmp_path / "notes.md"
    f.write_text("# Important\nKey decision: use SQLite.")
    result = load_jit(str(f))
    assert "Key decision" in result
    assert "SQLite" in result


def test_load_jit_by_query(tmp_path):
    """load_jit with a query ref searches files and returns matches."""
    (tmp_path / "a.py").write_text("def calculate_score():\n    return 42\n")
    (tmp_path / "b.py").write_text("x = 1\n")
    result = load_jit("calculate_score", search_root=tmp_path)
    assert "calculate_score" in result
    assert "42" in result


def test_summary_truncation():
    """truncate_response caps text at max_chars preserving sentence boundary."""
    long_text = "First sentence. " * 200  # ~3200 chars
    result = truncate_response(long_text, max_chars=200)
    assert len(result) <= 220  # small margin for sentence boundary
    assert result.endswith("[truncated]")
    assert "First sentence." in result


def test_compaction_trigger():
    """compact_context drops raw tool output blocks, keeps decision lines."""
    context = (
        "DECISION: Use approach A for the pipeline.\n"
        "--- RAW TOOL OUTPUT ---\n"
        "Line 1: some verbose tool dump\n"
        "Line 2: more verbose output\n"
        "Line 3: even more output\n"
        "--- END TOOL OUTPUT ---\n"
        "DECISION: Prioritize test coverage.\n"
        "Some other context that should stay.\n"
    )
    result = compact_context(context, max_chars=500)
    assert "Use approach A" in result
    assert "Prioritize test coverage" in result
    assert "verbose tool dump" not in result


def test_estimate_tokens():
    """estimate_tokens returns ~chars/4 approximation."""
    text = "a" * 400
    tokens = estimate_tokens(text)
    assert 90 <= tokens <= 110  # ~100 tokens for 400 chars
