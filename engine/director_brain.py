#!/usr/bin/env python3
"""Council-backed brain for the terminal director shell."""
import re


CHAT_CHAIRMAN_PROMPT = (
    "You are the brain of AutoAgent Agency speaking directly to the operator in a terminal. "
    "Respond in natural conversational language. No markdown. No headings. "
    "No numbered lists. No 'Recommendation:' label. Keep it concise, direct, and actionable. "
    "If there are multiple steps, weave them into plain prose. Under 220 words."
)

_MARKDOWN_RE = re.compile(r"[*_`]+")
_CONFIDENCE_RE = re.compile(r"\bconfidence\s*:\s*(high|medium|low)\b.*$", re.IGNORECASE)
_LABEL_RE = re.compile(r"^\s*(recommendation|immediate actions|strategic adjustments)\s*:?\s*$", re.IGNORECASE)


def _is_smalltalk(question: str) -> bool:
    """Return True for greetings / chit-chat that should not invoke the council."""
    q = " ".join(question.lower().split())
    if q in {"hi", "hello", "hey", "yo", "sup", "what's up", "whats up"}:
        return True
    if "how are you" in q or "hows it going" in q or "how's it going" in q:
        return True
    return False


def _quick_reply(question: str) -> str:
    """Fast non-council replies for greetings and light chatter."""
    q = " ".join(question.lower().split())
    if "how are you" in q or "hows it going" in q or "how's it going" in q:
        return "Online. Agency shell is up. Ask about a project, the orchestrator, or the council."
    return "Agency shell is up. How could I help you today?"


def _naturalize_reply(text: str) -> str:
    """Convert memo-like model output into plain chat text."""
    clean = _MARKDOWN_RE.sub("", text or "")
    clean = _CONFIDENCE_RE.sub("", clean).strip()

    lines = []
    for raw in clean.splitlines():
        line = " ".join(raw.split()).strip()
        if not line or _LABEL_RE.match(line):
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^\d+\.\s*", "", line)
        line = re.sub(r"^[-•]\s*", "", line)
        lines.append(line)

    compact = " ".join(lines).strip()
    compact = re.sub(r"\s+([,.!?;:])", r"\1", compact)
    compact = re.sub(r"\s{2,}", " ", compact)
    return compact[:1600]


def ask_brain(question: str, active_project: str | None = None) -> str:
    """Answer a free-text question using the multi-model council when possible."""
    from council import convene_council
    from director_helpers import get_agency_context
    from director_ai import ask_claude, _fallback_answer

    if _is_smalltalk(question):
        return _quick_reply(question)

    context = get_agency_context()
    if active_project:
        context += f"\n\nActive ship: {active_project}"
    result = convene_council(question, context=context, chairman_prompt=CHAT_CHAIRMAN_PROMPT)
    if "error" not in result:
        synthesis = (result.get("synthesis") or "").strip()
        if synthesis:
            return _naturalize_reply(synthesis)

    response = ask_claude(question)
    if response:
        return response
    return _fallback_answer(question)


def cmd_brain(cmd: str) -> str:
    question = cmd.split(maxsplit=1)[1].strip() if len(cmd.split(maxsplit=1)) > 1 else ""
    if not question:
        return "Usage: /brain <question>"
    return ask_brain(question)
