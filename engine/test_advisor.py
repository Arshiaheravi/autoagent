"""Unit tests for the advisor-pattern wrapper (engine/advisor.py)."""

from unittest.mock import MagicMock

import advisor


# ── helpers ──────────────────────────────────────────────────────────

class _TextBlock:
    """Mimics an SDK content block with .type and .text attributes."""
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


def _fake_response(texts: list[str]) -> MagicMock:
    """Build a fake SDK response whose .content holds the given text blocks."""
    resp = MagicMock()
    resp.content = [_TextBlock(t) for t in texts]
    return resp


def _fake_client(response=None) -> MagicMock:
    """Build a fake Anthropic client that returns the given response."""
    client = MagicMock()
    client.beta.messages.create.return_value = response or _fake_response(["ok"])
    return client


# ── system prompt shaping ────────────────────────────────────────────

def test_build_system_prompt_appends_advisor_rules():
    base = "You are a council chairman."
    out = advisor._build_system_prompt(base)
    assert base in out
    assert "advisor" in out.lower()
    assert "NO parameters" in out


def test_build_system_prompt_strips_trailing_whitespace_before_appending():
    out = advisor._build_system_prompt("SYS   \n\n")
    assert out.startswith("SYS")
    assert "advisor" in out.lower()


# ── tool payload shape ───────────────────────────────────────────────

def test_build_tools_declares_advisor_type_and_model():
    tools = advisor._build_tools("claude-opus-4-8")
    assert len(tools) == 1
    tool = tools[0]
    assert tool["type"] == advisor.ADVISOR_TOOL_TYPE
    assert tool["name"] == "advisor"
    assert tool["model"] == "claude-opus-4-8"


# ── advise() happy + failure paths ───────────────────────────────────

def test_advise_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert advisor.advise("sys", "task") == ""


def test_advise_returns_executor_text_on_success():
    client = _fake_client(_fake_response(["First block.", "Second block."]))
    out = advisor.advise("sys", "task", client=client)
    assert out == "First block.\nSecond block."


def test_advise_passes_correct_kwargs_to_sdk():
    client = _fake_client()
    advisor.advise(
        "sys",
        "question?",
        executor_model="exec-model",
        advisor_model="adv-model",
        max_tokens=512,
        client=client,
    )
    kwargs = client.beta.messages.create.call_args.kwargs
    assert kwargs["model"] == "exec-model"
    assert kwargs["max_tokens"] == 512
    assert advisor.ADVISOR_TOOL_BETA in kwargs["betas"]
    assert kwargs["tools"][0]["model"] == "adv-model"
    assert kwargs["messages"] == [{"role": "user", "content": "question?"}]
    assert "advisor" in kwargs["system"].lower()
    assert "sys" in kwargs["system"]


def test_advise_appends_extra_messages_after_task():
    client = _fake_client()
    extra = [{"role": "assistant", "content": "earlier turn"}]
    advisor.advise("sys", "task", extra_messages=extra, client=client)
    kwargs = client.beta.messages.create.call_args.kwargs
    assert kwargs["messages"][0] == {"role": "user", "content": "task"}
    assert kwargs["messages"][1] == extra[0]


def test_advise_returns_empty_string_on_sdk_exception():
    client = MagicMock()
    client.beta.messages.create.side_effect = RuntimeError("rate limited")
    assert advisor.advise("sys", "task", client=client) == ""


# ── _extract_text coverage ───────────────────────────────────────────

def test_extract_text_handles_dict_blocks():
    resp = MagicMock()
    resp.content = [{"type": "text", "text": "dict block"}]
    assert advisor._extract_text(resp) == "dict block"


def test_extract_text_skips_non_text_blocks():
    class ToolUse:
        def __init__(self):
            self.type = "tool_use"
            self.text = "should be ignored"

    resp = MagicMock()
    resp.content = [ToolUse(), _TextBlock("kept")]
    assert advisor._extract_text(resp) == "kept"


def test_extract_text_returns_empty_when_no_content_attribute():
    class Empty:
        pass
    assert advisor._extract_text(Empty()) == ""
