"""LLM Council — backend callers for each model provider."""
import contextvars
import json
import logging
import os
import shutil
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

try:
    from council_usage import (record_council_call, check_provider_budget,
                               check_tenant_budget)
except ImportError:
    def record_council_call(*args, **kwargs):  # type: ignore[misc]
        pass

    def check_provider_budget(*args, **kwargs):  # type: ignore[misc]
        return True, "council_usage unavailable — allowed"

    def check_tenant_budget(*args, **kwargs):  # type: ignore[misc]
        return True, "council_usage unavailable — allowed"


# Ambient tenant for the in-flight council, set by convene_council so every
# provider call in this call stack attributes spend to (and is gated by) the
# right tenant WITHOUT threading a param through all eight backend callers.
# Council runs sequentially (no thread fan-out) so a ContextVar is sufficient;
# None = agency-internal / single-tenant (untenanted global behaviour).
_current_tenant: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "council_current_tenant", default=None)


def set_council_tenant(tenant: str | None):
    """Bind the tenant for the current council run. Returns the ContextVar
    token — pass it to reset_council_tenant() in a finally block."""
    return _current_tenant.set(tenant)


def reset_council_tenant(token) -> None:
    """Restore the tenant binding captured by set_council_tenant()."""
    try:
        _current_tenant.reset(token)
    except Exception:
        pass


def _record_usage(**kwargs):
    """Best-effort usage logging; never fail an otherwise valid model answer."""
    try:
        kwargs.setdefault("tenant", _current_tenant.get())
        record_council_call(**kwargs)
    except Exception as e:
        logger.warning("Council usage logging failed: %s", e)


def _budget_gate(provider: str) -> bool:
    """Hard pre-call spend gate. Returns False (and logs) when the provider is
    over its monthly budget OR the in-flight tenant is over its comped-council
    cap, so the caller skips the API call. Any gate error fails open — see
    council_usage.check_provider_budget / check_tenant_budget."""
    tenant = _current_tenant.get()
    tok, treason = check_tenant_budget(tenant)
    if not tok:
        logger.warning("[Council] tenant cap BLOCKED %s — %s", provider, treason)
        return False
    ok, reason = check_provider_budget(provider)
    if not ok:
        logger.warning("[Council] budget gate BLOCKED %s — %s", provider, reason)
    return ok


def _find_claude() -> str:
    path = shutil.which("claude")
    if path:
        return path
    return "claude"


def _call_claude(prompt: str, max_turns: int = 1, timeout: int = 600) -> str:
    """Call Claude. Prefer CLI subprocess (Max-plan billing); fall back to
    API when CLI is unavailable. 600s default — long council prompts (50k+
    chars) routinely exceed shorter limits."""
    claude = _find_claude()
    try:
        result = subprocess.run(
            [claude, "-p", prompt, "--output-format", "text",
             "--max-turns", str(max_turns)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return ""
    except FileNotFoundError:
        logger.warning("Claude CLI not found, trying API fallback")
        return _call_claude_api(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("Claude CLI timed out after %ds", timeout)
        return ""
    except Exception as e:
        logger.warning("Claude CLI call failed: %s", e)
        return ""


def _call_claude_api(prompt: str, timeout: int = 300) -> str:
    """Call Anthropic Messages API directly and return text response."""
    api_key = (os.environ.get("COUNCIL_ANTHROPIC_API_KEY")
               or os.environ.get("ANTHROPIC_API_KEY", ""))
    if not api_key:
        return ""
    if not _budget_gate("anthropic"):
        return ""
    # Default to Opus 4.8 per the operator's council-top-tier pin (drop-in for
    # 4.7, same API surface + pricing). Override via $COUNCIL_ANTHROPIC_MODEL.
    # Hoisted so the request and the usage-logging fallback below share ONE id
    # — a real, priced MODEL_PRICING key. (Was "claude-sonnet", absent from the
    # pricing/provider tables → $0 logged under provider "other".)
    model_id = os.environ.get("COUNCIL_ANTHROPIC_MODEL", "claude-opus-4-8")
    try:
        import requests
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        data = resp.json()
        content = data.get("content", [])
        if content:
            text = content[0].get("text", "").strip()
            usage = data.get("usage", {})
            _record_usage(
                model=data.get("model", model_id),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )
            return text
        return ""
    except Exception as e:
        logger.warning("Anthropic API call failed: %s", e)
        return ""


def _call_codex(prompt: str, timeout: int = 300) -> str:
    """Call OpenAI via API. Returns text response.

    GPT-5.5 is a reasoning model — reasoning_tokens consume the
    max_completion_tokens budget before any visible content. On long
    council prompts the reasoning alone runs 5–15k tokens. 16384 budget
    + reasoning_effort=medium leaves headroom for visible output.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return ""
    if not _budget_gate("openai"):
        return ""
    try:
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("COUNCIL_OPENAI_MODEL", "gpt-5.5"),
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 16384,
                "reasoning_effort": "medium",
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning("OpenAI HTTP %d: %s", resp.status_code, resp.text[:300])
            return ""
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "").strip()
        usage = data.get("usage", {})
        if not text:
            comp = usage.get("completion_tokens_details", {})
            logger.warning(
                "OpenAI returned empty content (finish_reason=%s, reasoning_tokens=%s, completion_tokens=%s)",
                choice.get("finish_reason"),
                comp.get("reasoning_tokens"),
                usage.get("completion_tokens"),
            )
            return ""
        _record_usage(
            model=os.environ.get("COUNCIL_OPENAI_MODEL", "gpt-5.5"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
        return text
    except Exception as e:
        logger.warning("OpenAI API call failed: %s", e)
        return ""


def _call_gemini(prompt: str, timeout: int = 180) -> str:
    """Call Gemini with a reliability-first model order. Top-tier first per
    council policy. 2.0-flash dropped 2026-05 — deprecated by Google."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ""
    if not _budget_gate("gemini"):
        return ""

    models = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed")
        return ""

    for model in models:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.3},
                },
                timeout=timeout,
            )

            if resp.status_code == 429:
                logger.info("Gemini %s rate-limited, trying next model", model)
                time.sleep(2)
                continue

            if resp.status_code == 503:
                logger.info("Gemini %s overloaded, trying next model", model)
                time.sleep(1)
                continue

            if resp.status_code >= 400:
                body = resp.text[:200]
                if "not found" in body.lower() or "not supported" in body.lower():
                    logger.info("Gemini %s not available: %s", model, body[:100])
                    continue
                logger.warning("Gemini %s HTTP %d: %s", model, resp.status_code, body)
                continue

            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "").strip()
                    if text:
                        usage = data.get("usageMetadata", {})
                        _record_usage(
                            model=f"gemini:{model}",
                            input_tokens=usage.get("promptTokenCount", 0),
                            output_tokens=usage.get("candidatesTokenCount", 0),
                        )
                        return text

            prompt_feedback = data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason", "")
            if block_reason:
                logger.warning("Gemini %s blocked: %s", model, block_reason)
                continue

            logger.info("Gemini %s returned empty, trying next", model)

        except requests.exceptions.Timeout:
            logger.info("Gemini %s timed out after %ds, trying next", model, timeout)
            continue
        except Exception as e:
            logger.warning("Gemini %s failed: %s", model, e)
            continue

    logger.warning("All Gemini models failed")
    return ""


def _call_deepseek(prompt: str, timeout: int = 180) -> str:
    """Call DeepSeek via API. Returns text response.

    Model defaults to `deepseek-reasoner` (DeepSeek's top-tier reasoning
    model — per the operator's council-top-tier pin) and can be overridden
    via `$COUNCIL_DEEPSEEK_MODEL`."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""
    if not _budget_gate("deepseek"):
        return ""
    model = os.environ.get("COUNCIL_DEEPSEEK_MODEL", "deepseek-reasoner")
    try:
        import requests
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
                "temperature": 0.3,
            },
            timeout=timeout,
        )
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        usage = data.get("usage", {})
        _record_usage(
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
        return text
    except Exception as e:
        logger.warning("DeepSeek API call failed: %s", e)
        return ""


def _call_grok(prompt: str, timeout: int = 180) -> str:
    """Call xAI Grok via OpenAI-compatible API. Returns text response.

    xAI applies aggressive safety filters (e.g. SAFETY_CHECK_TYPE_BIO) that can
    return HTTP 403 with no `choices` field. We log the refusal explicitly so
    the council surface knows Grok was attempted and rejected, instead of
    silently dropping the persona.
    """
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        logger.info("Grok skipped: XAI_API_KEY not set")
        return ""
    if not _budget_gate("xai"):
        return ""
    try:
        import requests
        resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("COUNCIL_GROK_MODEL", "grok-4"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
                "temperature": 0.3,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            body = resp.text[:500]
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", body)
            except Exception:
                err_msg = body
            err_str = str(err_msg).lower()
            if resp.status_code in (402, 429) or "credit" in err_str or "billing" in err_str or "quota" in err_str:
                logger.warning("Grok billing/quota issue (HTTP %d) — top up xAI credits: %s",
                               resp.status_code, err_msg)
            elif resp.status_code == 403 and "safety_check" in err_str:
                logger.warning("Grok refused (safety filter): %s", err_msg)
            else:
                logger.warning("Grok HTTP %d: %s", resp.status_code, err_msg)
            return ""
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("Grok returned no choices: %s", str(data)[:300])
            return ""
        text = choices[0].get("message", {}).get("content", "").strip()
        if not text:
            logger.warning("Grok returned empty content (finish_reason=%s)",
                           choices[0].get("finish_reason"))
            return ""
        usage = data.get("usage", {})
        _record_usage(
            model=os.environ.get("COUNCIL_GROK_MODEL", "grok-4"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
        return text
    except Exception as e:
        logger.warning("xAI Grok API call failed: %s", e)
        return ""


def _call_with_fallback(prompt: str, backends: tuple[str, ...], timeout: int = 300) -> str:
    """Try multiple council backends in order until one returns text."""
    dispatch = {
        "claude": _call_claude,
        "openai": _call_codex,
        "gemini": _call_gemini,
        "deepseek": _call_deepseek,
        "grok": _call_grok,
    }
    for backend in backends:
        fn = dispatch.get(backend)
        if fn:
            result = fn(prompt, timeout=timeout)
            if result:
                return result
    return ""


def _call_gemini_vision(prompt: str, image_path: str, timeout: int = 120) -> str:
    """Call Gemini with an image for visual analysis."""
    import base64
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ""
    if not _budget_gate("gemini"):
        return ""
    try:
        import requests
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": image_data}},
                    ]
                }],
                "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.3},
            },
            timeout=timeout,
        )
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        return ""
    except Exception as e:
        logger.warning("Gemini vision call failed: %s", e)
        return ""


def _call_openai_vision(prompt: str, image_path: str, timeout: int = 120) -> str:
    """Call GPT-5.4 with an image for visual analysis."""
    import base64
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return ""
    if not _budget_gate("openai"):
        return ""
    try:
        import requests
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("COUNCIL_OPENAI_MODEL", "gpt-5.5"),
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    ],
                }],
                "max_completion_tokens": 1000,
                "temperature": 0.3,
            },
            timeout=timeout,
        )
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning("OpenAI vision call failed: %s", e)
        return ""
