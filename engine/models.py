"""Single source of truth for Anthropic model IDs and per-session-type defaults.

Every engine module that needs a Claude model id imports it from here. Do NOT
hardcode `claude-*` strings elsewhere — a model launch then becomes a one-file
change instead of a scattered grep-and-replace.

Pricing lives in council_usage.py (MODEL_PRICING), which also carries older ids
for historical-row back-compat; keep the CURRENT ids below in sync with it.
"""
from __future__ import annotations

from typing import Any

# ── Current Claude family (2026-07). IDs are complete as-is — never append a
#    date suffix (except Haiku's, which the API accepts either way). ──
FABLE_5 = "claude-fable-5"      # most capable; different API surface (thinking always on)
OPUS_4_8 = "claude-opus-4-8"    # top Opus-tier; deliberation default
SONNET_5 = "claude-sonnet-5"    # near-Opus coding/agentic at Sonnet cost
HAIKU_4_5 = "claude-haiku-4-5"  # fastest/cheapest; simple tasks

# Default model for a fresh project/agency when config names none.
DEFAULT_MODEL = OPUS_4_8

# Default daily API spend cap (USD) for a project whose config omits
# `daily_limit_usd`. SSoT so the writer (intake) and the readers (budget gate,
# cost predictor, status) can't drift — they used to split 50.0 vs 15.0.
# Only enforced in API mode; a documented no-op under CLI/Max routing.
DEFAULT_DAILY_LIMIT_USD = 50.0

# Per-session-type tier defaults. Work sessions run the cheaper near-Opus tier;
# deliberation sessions (meta/brain/deep/audit) run Opus. Overridable per project
# via config `models.{type}` or top-level `model`.
SESSION_MODEL_DEFAULTS: dict[str, str] = {
    "work": SONNET_5,
    "meta": OPUS_4_8,
    "brain": OPUS_4_8,
    "deep": OPUS_4_8,
    "audit": OPUS_4_8,
}


def default_model_for_session(session_type: str) -> str:
    """Tier default for a session type, falling back to DEFAULT_MODEL."""
    return SESSION_MODEL_DEFAULTS.get(session_type, DEFAULT_MODEL)


def resolve_model(config: dict[str, Any] | None, session_type: str) -> str:
    """Resolve the model for a session.

    Precedence: config `models.{session_type}` → config top-level `model` →
    the SSoT tier default. Always returns a real id so callers never have to
    guard against a missing model.
    """
    config = config or {}
    models_map = config.get("models") or {}
    return (
        models_map.get(session_type)
        or config.get("model")
        or default_model_for_session(session_type)
    )
