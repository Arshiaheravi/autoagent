"""Model fallback — when Claude CLI hits rate limits, route to the best available model.

Task-aware routing: instead of a dumb chain, each task type maps to the model
that excels at it. Falls through to the next best if the preferred model has no key.

    Claude (primary) → task-aware fallback → generic chain

Usage:
    from model_fallback import run_fallback, is_rate_limit_error
    if is_rate_limit_error(error_text):
        success, model, response = run_fallback(prompt, task_type="work")
"""
import logging
import os
import re

logger = logging.getLogger(__name__)


# ── Task-to-model routing ─────────────────────────────────────────
# Each task type has a preferred model order based on strengths.
# "work" = code generation, debugging, tests → GPT-5.4 first (strongest coder)
# "meta" = prompt improvement, failure analysis → Sonnet first (good writing, free bucket)
# "brain" = web research, architecture → Gemini first (synthesis, planning)
# "deep" = combined meta+brain → Gemini first
# "review" = code review, security audit → GPT-5.4 first (spotting issues)
# "algorithm" = data processing, bulk changes → DeepSeek first (precise, code-focused)
# "copy" = copywriting, content, marketing → Sonnet first (best copywriter, free bucket)
# "docs" = documentation, README, guides → Sonnet first (clear writing, free bucket)

TASK_ROUTING = {
    "work": ["gpt-5.4", "deepseek-v3", "gemini-3.1-pro-preview"],
    "meta": ["claude-sonnet", "gemini-3.1-pro-preview", "gpt-5.4"],
    "brain": ["gemini-3.1-pro-preview", "gpt-5.4", "deepseek-v3"],
    "deep": ["gemini-3.1-pro-preview", "claude-sonnet", "gpt-5.4"],
    "review": ["gpt-5.4", "gemini-3.1-pro-preview", "deepseek-v3"],
    "algorithm": ["deepseek-v3", "gpt-5.4", "gemini-3.1-pro-preview"],
    "copy": ["claude-sonnet", "gpt-5.4", "gemini-3.1-pro-preview"],
    "docs": ["claude-sonnet", "gemini-3.1-pro-preview", "gpt-5.4"],
}

# Default chain if task type isn't recognized
DEFAULT_CHAIN = ["gpt-5.4", "gemini-3.1-pro-preview", "deepseek-v3"]


# ── Model registry ────────────────────────────────────────────────

MODELS = {
    "claude-sonnet": {
        "env_key": "_CLAUDE_CLI",
        "label": "Claude Sonnet",
        "strengths": "copywriting, content, documentation, meta-analysis",
    },
    "gpt-5.4": {
        "env_key": "OPENAI_API_KEY",
        "label": "GPT-5.4",
        "strengths": "code generation, debugging, code review",
    },
    "gemini-3.1-pro-preview": {
        "env_key": "GEMINI_API_KEY",
        "label": "Gemini 3.1 Pro Preview",
        "strengths": "architecture, planning, long context, research",
    },
    "deepseek-v3": {
        "env_key": "DEEPSEEK_API_KEY",
        "label": "DeepSeek V3",
        "strengths": "algorithmic code, data processing, bulk changes",
    },
}


# ── Rate limit detection ──────────────────────────────────────────

_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|429|too many requests|overloaded|"
    r"503|service unavailable|capacity|throttl|"
    r"usage.?limit|quota.?exceeded|"
    r"(daily|weekly|monthly)\s+(usage\s+)?limit|"
    r"(opus|sonnet|claude)\s+(weekly\s+)?usage\s+limit|"
    r"out of (extra\s+)?usage|extra\s+usage|"
    r"limit\s+(has\s+been\s+)?reached|"
    r"credits?\s+(exhausted|depleted)|insufficient\s+credits",
    re.IGNORECASE,
)


def is_rate_limit_error(error_text: str) -> bool:
    """Check if error text indicates a rate limit / capacity issue."""
    return bool(_RATE_LIMIT_RE.search(error_text))


# ── API callers ───────────────────────────────────────────────────

def _call_sonnet(prompt: str, timeout: int = 300) -> str:
    """Call Claude Sonnet via CLI. Uses the separate Sonnet usage bucket (free on Max plan)."""
    import shutil
    import subprocess
    from pathlib import Path

    claude = shutil.which("claude") or "claude"
    try:
        result = subprocess.run(
            [claude, "-p", prompt, "--model", "sonnet",
             "--max-turns", "1", "--output-format", "text"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
            cwd=str(Path.home()),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        raise RuntimeError(f"Sonnet CLI error: exit {result.returncode}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Sonnet CLI timed out")


def _call_gemini(prompt: str, timeout: int = 300) -> str:
    """Call Gemini 2.5 Pro and return the full response text."""
    import requests

    api_key = os.environ.get("GEMINI_API_KEY", "")
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 8192,
                "temperature": 0.3,
            },
        },
        timeout=timeout,
    )
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "").strip()
    error_msg = data.get("error", {}).get("message", "Unknown Gemini error")
    raise RuntimeError(f"Gemini API error: {error_msg}")


def _call_deepseek(prompt: str, timeout: int = 300) -> str:
    """Call DeepSeek V3 and return the full response text."""
    import requests

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
            "temperature": 0.3,
        },
        timeout=timeout,
    )
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content:
        return content.strip()
    error_msg = data.get("error", {}).get("message", "Unknown DeepSeek error")
    raise RuntimeError(f"DeepSeek API error: {error_msg}")


def _call_openai(prompt: str, timeout: int = 300) -> str:
    """Call GPT-4o and return the full response text."""
    import requests

    api_key = os.environ.get("OPENAI_API_KEY", "")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": 8192,
            "temperature": 0.3,
        },
        timeout=timeout,
    )
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content:
        return content.strip()
    error_msg = data.get("error", {}).get("message", "Unknown OpenAI error")
    raise RuntimeError(f"OpenAI API error: {error_msg}")


_DISPATCH = {
    "claude-sonnet": _call_sonnet,
    "gemini-3.1-pro-preview": _call_gemini,
    "deepseek-v3": _call_deepseek,
    "gpt-5.4": _call_openai,
}


# ── Core fallback logic ──────────────────────────────────────────

def _get_chain_for_task(task_type: str) -> list[str]:
    """Return the model priority chain for a given task type."""
    return TASK_ROUTING.get(task_type, DEFAULT_CHAIN)


def run_fallback(
    prompt: str,
    task_type: str = "work",
    timeout: int = 300,
) -> tuple[bool, str, str]:
    """Route to the best available model for this task type.

    Args:
        prompt: The full boot prompt to send.
        task_type: Session type — "work", "meta", "brain", "deep", "review", "algorithm".
        timeout: Request timeout in seconds.

    Returns:
        (success, model_name, response_text)
    """
    chain = _get_chain_for_task(task_type)
    tried = []

    for model_name in chain:
        model = MODELS.get(model_name)
        if not model:
            continue

        # Sonnet uses CLI (always available), others need API keys
        if model["env_key"] != "_CLAUDE_CLI":
            api_key = os.environ.get(model["env_key"], "")
            if not api_key:
                continue

        call_fn = _DISPATCH.get(model_name)
        if not call_fn:
            continue

        label = model["label"]
        strengths = model["strengths"]
        tried.append(label)

        try:
            logger.info("Falling back to %s (best for: %s)", label, strengths)
            print(
                f"\n  [AutoAgent] Claude rate-limited. "
                f"Routing {task_type} task to {label} ({strengths})...",
                flush=True,
            )
            response = call_fn(prompt, timeout=timeout)
            if response:
                print(f"  [AutoAgent] {label} responded ({len(response)} chars)", flush=True)
                return True, model_name, response
        except Exception as exc:
            logger.warning("Fallback %s failed: %s", label, exc)
            print(f"  [AutoAgent] {label} failed: {exc}", flush=True)
            continue

    tried_str = ", ".join(tried) if tried else "none available"
    return False, "", f"All fallback models failed (tried: {tried_str})"


# ── Status ────────────────────────────────────────────────────────

def get_fallback_status() -> dict:
    """Return which fallback models are available and their strengths."""
    status = {}
    for name, model in MODELS.items():
        if model["env_key"] == "_CLAUDE_CLI":
            import shutil
            state = "ready (CLI)" if shutil.which("claude") else "no CLI"
        else:
            key = os.environ.get(model["env_key"], "")
            state = "ready" if key else "no key"
        status[model["label"]] = {
            "state": state,
            "strengths": model["strengths"],
        }
    return status
