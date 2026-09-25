"""Unit tests for council.backends — covers API callers, fallback chains, vision."""

import subprocess
from unittest.mock import patch, MagicMock

import council.backends as backends


# ── budget gate — over-budget provider is blocked pre-call ─────────

def test_backend_blocked_when_over_budget(monkeypatch):
    # Key present so an empty return can only come from the budget gate,
    # which fires before any `import requests` / HTTP call in the backend.
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(backends, "check_provider_budget",
                        lambda prov: (False, "over budget"))
    assert backends._call_gemini("q", timeout=5) == ""


def test_backend_proceeds_when_under_budget(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # key check still gates first
    monkeypatch.setattr(backends, "check_provider_budget", lambda prov: (True, "ok"))
    assert backends._call_gemini("q", timeout=5) == ""


# ── tenant cap gate — bound tenant over cap blocks every provider call ─────

def test_backend_blocked_when_tenant_over_cap(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(backends, "check_provider_budget", lambda prov: (True, "ok"))
    monkeypatch.setattr(backends, "check_tenant_budget",
                        lambda t: (False, "over council cap") if t else (True, "ok"))
    tok = backends.set_council_tenant("acme")
    try:
        assert backends._call_gemini("q", timeout=5) == ""  # tenant gate fires
    finally:
        backends.reset_council_tenant(tok)


def test_tenant_gate_noop_when_unbound(monkeypatch):
    # No tenant bound → tenant gate must not block; provider gate/key still apply.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(backends, "check_provider_budget", lambda prov: (True, "ok"))
    called = {"tenant": "sentinel"}

    def _capture(t):
        called["tenant"] = t
        return (True, "ok")
    monkeypatch.setattr(backends, "check_tenant_budget", _capture)
    backends._budget_gate("gemini")
    assert called["tenant"] is None  # unbound context passes None through


def test_set_reset_tenant_no_leak(monkeypatch):
    tok = backends.set_council_tenant("acme")
    backends.reset_council_tenant(tok)
    seen = {}
    monkeypatch.setattr(backends, "check_provider_budget", lambda prov: (True, "ok"))
    monkeypatch.setattr(backends, "check_tenant_budget",
                        lambda t: seen.setdefault("t", t) or (True, "ok"))
    backends._budget_gate("gemini")
    assert seen["t"] is None  # reset restored the unbound default


# ── _call_claude — FileNotFoundError triggers API fallback ─────────

def test_call_claude_file_not_found_falls_back_to_api():
    with patch("council.backends.subprocess.run", side_effect=FileNotFoundError), \
         patch("council.backends._call_claude_api", return_value="api answer") as mock_api:
        result = backends._call_claude("hello")
    assert result == "api answer"
    mock_api.assert_called_once_with("hello", timeout=600)


def test_call_claude_generic_exception_returns_empty():
    with patch("council.backends.subprocess.run", side_effect=RuntimeError("boom")):
        assert backends._call_claude("q") == ""


def test_call_claude_empty_stdout_returns_empty():
    fake = MagicMock(returncode=0, stdout="   \n  ")
    with patch("council.backends.subprocess.run", return_value=fake):
        assert backends._call_claude("q") == ""


# ── _call_claude_api ───────────────────────────────────────────────

def test_call_claude_api_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert backends._call_claude_api("q") == ""


def test_call_claude_api_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"text": "answer from API"}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
        "model": "claude-sonnet-4-20250514",
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_claude_api("q")
    assert result == "answer from API"


def test_call_claude_api_empty_content(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"content": []}
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_claude_api("q")
    assert result == ""


def test_call_claude_api_exception_returns_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = ConnectionError("down")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_claude_api("q")
    assert result == ""


def test_call_claude_api_missing_model_logs_real_priced_id(monkeypatch):
    # When the API response omits "model", usage must be attributed to a REAL
    # priced id (the model we actually requested) — not the old "claude-sonnet"
    # default, which is absent from MODEL_PRICING/MODEL_PROVIDER (→ $0 / "other").
    import council_usage as cu
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("COUNCIL_ANTHROPIC_MODEL", raising=False)
    captured = {}
    monkeypatch.setattr(backends, "_record_usage",
                        lambda **kw: captured.update(kw))
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"text": "hi"}],
        "usage": {"input_tokens": 5, "output_tokens": 7},
        # NOTE: no "model" key — forces the fallback default
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_claude_api("q") == "hi"
    assert captured["model"] == "claude-opus-4-8"
    assert captured["model"] in cu.MODEL_PRICING  # real, priced
    assert cu.MODEL_PROVIDER.get(captured["model"]) == "anthropic"


# ── _call_codex ────────────────────────────────────────────────────

def test_call_codex_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "codex says hi"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_codex("q")
    assert result == "codex says hi"


def test_call_codex_ignores_usage_logging_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "codex says hi"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}), \
         patch("council.backends.record_council_call", side_effect=OSError("readonly")):
        result = backends._call_codex("q")
    assert result == "codex says hi"


def test_call_codex_exception_returns_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("fail")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_codex("q") == ""


# ── _call_gemini — multi-model fallback chain ──────────────────────

def test_call_gemini_success_first_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "gemini answer"}]}}],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10},
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == "gemini answer"
    assert mock_requests.post.call_count == 1


def test_call_gemini_rate_limit_tries_next_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_429 = MagicMock(status_code=429)
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "from flash"}]}}],
        "usageMetadata": {},
    }
    mock_requests = MagicMock()
    mock_requests.post.side_effect = [resp_429, resp_ok]
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}), \
         patch("council.backends.time.sleep"):
        result = backends._call_gemini("q")
    assert result == "from flash"
    assert mock_requests.post.call_count == 2


def test_call_gemini_503_overloaded_tries_next(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_503 = MagicMock(status_code=503)
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "backup model"}]}}],
        "usageMetadata": {},
    }
    mock_requests = MagicMock()
    mock_requests.post.side_effect = [resp_503, resp_ok]
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}), \
         patch("council.backends.time.sleep"):
        result = backends._call_gemini("q")
    assert result == "backup model"


def test_call_gemini_not_found_skips_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_404 = MagicMock(status_code=404, text="model not found in region")
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "fallback"}]}}],
        "usageMetadata": {},
    }
    mock_requests = MagicMock()
    mock_requests.post.side_effect = [resp_404, resp_ok]
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == "fallback"


def test_call_gemini_blocked_prompt_tries_next(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_blocked = MagicMock(status_code=200)
    resp_blocked.json.return_value = {
        "candidates": [],
        "promptFeedback": {"blockReason": "SAFETY"},
    }
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {},
    }
    mock_requests = MagicMock()
    mock_requests.post.side_effect = [resp_blocked, resp_ok]
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == "ok"


def test_call_gemini_all_fail_returns_empty(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_fail = MagicMock(status_code=500, text="internal error")
    mock_requests = MagicMock()
    mock_requests.post.return_value = resp_fail
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == ""
    assert mock_requests.post.call_count == 2


def test_call_gemini_timeout_tries_next(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    mock_requests = MagicMock()
    timeout_exc = type("Timeout", (Exception,), {})
    mock_requests.exceptions.Timeout = timeout_exc
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "after timeout"}]}}],
        "usageMetadata": {},
    }
    mock_requests.post.side_effect = [timeout_exc(), resp_ok]
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == "after timeout"


def test_call_gemini_empty_candidates_tries_next(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    resp_empty = MagicMock(status_code=200)
    resp_empty.json.return_value = {"candidates": [{"content": {"parts": []}}]}
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "got it"}]}}],
        "usageMetadata": {},
    }
    mock_requests = MagicMock()
    mock_requests.post.side_effect = [resp_empty, resp_ok]
    mock_requests.exceptions = MagicMock()
    mock_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini("q")
    assert result == "got it"


# ── _call_deepseek ─────────────────────────────────────────────────

def test_call_deepseek_success(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "deepseek answer"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_deepseek("q")
    assert result == "deepseek answer"


def test_call_deepseek_exception_returns_empty(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("boom")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_deepseek("q") == ""


# ── _call_grok ─────────────────────────────────────────────────────

def test_call_grok_success(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "grok says"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 7},
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_grok("q")
    assert result == "grok says"


def test_call_grok_safety_refusal_returns_empty(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"error":"... Failed check: SAFETY_CHECK_TYPE_BIO"}'
    mock_resp.json.return_value = {
        "code": "denied",
        "error": "Content violates usage guidelines. Failed check: SAFETY_CHECK_TYPE_BIO",
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_grok("q") == ""


def test_call_grok_exception_returns_empty(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("down")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_grok("q") == ""


# ── Vision callers ─────────────────────────────────────────────────

def test_call_gemini_vision_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert backends._call_gemini_vision("describe", "/tmp/img.png") == ""


def test_call_gemini_vision_success(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG fake image data")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "I see a chart"}]}}],
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_gemini_vision("describe", str(img))
    assert result == "I see a chart"


def test_call_gemini_vision_exception_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("vision fail")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_gemini_vision("describe", str(img)) == ""


def test_call_openai_vision_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert backends._call_openai_vision("describe", "/tmp/img.png") == ""


def test_call_openai_vision_success(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG fake")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "openai sees a dashboard"}}],
    }
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp
    with patch.dict("sys.modules", {"requests": mock_requests}):
        result = backends._call_openai_vision("describe", str(img))
    assert result == "openai sees a dashboard"


def test_call_openai_vision_exception_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG")
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("fail")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert backends._call_openai_vision("describe", str(img)) == ""
