"""LLM Council — multi-model decision support.

Thin re-export shim. All functionality lives in submodules:
    council.backends  — model provider callers
    council.personas  — persona definitions and prompt constants
    council.executive — 3-stage pipeline, public API
    council.reviews   — codex review, UX review, design council
"""
from .backends import (  # noqa: F401
    record_council_call,
    _find_claude,
    _call_claude,
    _call_claude_api,
    _call_codex,
    _call_gemini,
    _call_deepseek,
    _call_grok,
    _call_with_fallback,
    _call_gemini_vision,
    _call_openai_vision,
)
from .personas import (  # noqa: F401
    PERSONAS,
    EXECUTIVE_REVIEWERS,
    CHAIRMAN_PROMPT,
    DESIGN_REVIEW_PROMPT,
    _FRONTEND_EXTENSIONS,
)
from .executive import (  # noqa: F401
    _build_executive_review_prompt,
    _collect_from_specs,
    _stage1_collect,
    _stage2_rank,
    _parse_ranking,
    _aggregate_rankings,
    _stage3_synthesize,
    convene_council,
    convene_council_with_debate,
    council_pick_task,
)
from .reviews import (  # noqa: F401
    codex_review,
    _has_frontend_changes,
    ux_review,
    design_council,
)
