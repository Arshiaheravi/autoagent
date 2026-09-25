"""Advisor pattern wrapper — Sonnet executor + Opus advisor via Anthropic SDK.

Background:
    Global ~/.claude/CLAUDE.md mandates the Advisor pattern as the default
    for autonomous agents. Sonnet runs the main loop (cheap, fast) and
    consults Opus via the `advisor_20260301` beta tool at decision points.
    Cost savings vs running Opus straight-through: ~3-5× on deliberation.

Scope of THIS file:
    Thin wrapper that exposes `advise(...)` returning the executor's final
    text for a given task. Uses the Anthropic SDK beta advisor tool. No
    state, no retries, no SDK version pinning — caller owns retries and
    the budget cap (config.json `session_max_usd`).

Integration status:
    Written 2026-04-16 as audit §6b remediation. NOT yet wired into the
    main brain/meta session path — that is a separate follow-up that
    touches engine/run.py. For now this module stands alone so the SDK
    surface and prompt shape can be exercised in isolation, and tests
    live in engine/test_advisor.py.

Usage:
    from advisor import advise
    text = advise(
        system_prompt="You are the chairman...",
        task="Should we deploy this migration?",
        executor_model="claude-sonnet-5",
        advisor_model="claude-opus-4-8",
        max_tokens=2048,
    )
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_EXECUTOR = "claude-sonnet-5"
DEFAULT_ADVISOR = "claude-opus-4-8"
ADVISOR_TOOL_BETA = "advisor-tool-2026-03-01"
ADVISOR_TOOL_TYPE = "advisor_20260301"


def _build_tools(advisor_model: str) -> list[dict]:
    return [{
        "type": ADVISOR_TOOL_TYPE,
        "name": "advisor",
        "model": advisor_model,
    }]


def _build_system_prompt(base_system: str) -> str:
    """Append advisor-call discipline to the caller's system prompt.

    The executor needs explicit triggers for when to call advisor()
    otherwise it either never calls (no cost win) or calls on every turn
    (no latency win, no cost win).
    """
    advisor_rules = (
        "\n\n## Advisor tool\n"
        "You have a single `advisor` tool backed by a stronger reviewer model. "
        "It takes NO parameters — calling advisor() forwards the full conversation.\n\n"
        "Call advisor BEFORE substantive work — before committing to an interpretation, "
        "before building on an assumption, before finalizing a deliverable. Orientation "
        "(finding files, fetching sources, skimming) is not substantive work — do that "
        "first, then call advisor.\n\n"
        "Also call advisor:\n"
        "- When you believe the task is complete (make deliverable durable BEFORE the call)\n"
        "- When stuck (errors recurring, approach not converging)\n"
        "- When considering a change of approach\n\n"
        "The advisor returns under 100 words with enumerated steps. Follow them."
    )
    return (base_system.rstrip() + advisor_rules).strip()


def advise(
    system_prompt: str,
    task: str,
    executor_model: str = DEFAULT_EXECUTOR,
    advisor_model: str = DEFAULT_ADVISOR,
    max_tokens: int = 2048,
    extra_messages: Optional[list[dict]] = None,
    client: Any = None,
) -> str:
    """Run an advisor-pattern turn and return the executor's final text.

    Args:
        system_prompt: Caller's system prompt (advisor rules are appended).
        task: The user-facing task / question.
        executor_model: Model running the main loop (default Sonnet 4.6).
        advisor_model: Model consulted for judgment calls (default Opus 4.7).
        max_tokens: Cap for the executor response (advisor has its own).
        extra_messages: Optional prior turns to append after the task.
        client: Override Anthropic client (for tests). If None, a default
            Anthropic() client is created — requires ANTHROPIC_API_KEY.

    Returns:
        The concatenated text from the executor's final turn. Empty string
        if the SDK call fails or the API key is missing.
    """
    if client is None:
        advisor_key = (os.environ.get("COUNCIL_ANTHROPIC_API_KEY")
                       or os.environ.get("ANTHROPIC_API_KEY"))
        if not advisor_key:
            logger.warning("advise() skipped — no ANTHROPIC/COUNCIL_ANTHROPIC key set")
            return ""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=advisor_key)
        except Exception as e:
            logger.warning("advise() skipped — SDK init failed: %s", e)
            return ""

    messages = [{"role": "user", "content": task}]
    if extra_messages:
        messages.extend(extra_messages)

    try:
        response = client.beta.messages.create(
            model=executor_model,
            max_tokens=max_tokens,
            betas=[ADVISOR_TOOL_BETA],
            system=_build_system_prompt(system_prompt),
            tools=_build_tools(advisor_model),
            messages=messages,
        )
    except Exception as e:
        logger.warning("advise() SDK call failed: %s", e)
        return ""

    return _extract_text(response)


def _extract_text(response: Any) -> str:
    """Flatten response.content text blocks into a single string."""
    content = getattr(response, "content", None)
    if content is None:
        return ""
    parts: list[str] = []
    for block in content:
        # SDK returns objects with .type and .text OR dicts; handle both.
        block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if block_type != "text":
            continue
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    return "\n".join(parts).strip()
