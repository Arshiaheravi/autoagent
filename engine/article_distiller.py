#!/usr/bin/env python3
"""Article Distiller — extract actionable knowledge from articles and screenshots.

Accepts raw text or a Telegram photo (as bytes), calls Claude with vision support,
scores practical value, checks for redundancy, and files high-quality insights into
brain/distilled.md. Everything gets archived regardless.

Usage:
    from article_distiller import distill_text, distill_image
    result = distill_text("paste of article...")
    result = distill_image(image_bytes, mime_type="image/jpeg")
    # result: {"filed": True/False, "summary": str, "rule": str, "score": int}
"""
import base64
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────

AUTOAGENT_ROOT = Path(__file__).parent.parent
BRAIN_DIR = AUTOAGENT_ROOT / "brain"
ARTICLES_DIR = BRAIN_DIR / "articles"
DISTILLED_PATH = BRAIN_DIR / "distilled.md"

ARTICLES_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────

def _load_existing_knowledge(max_lines: int = 80) -> str:
    """Load a summary of already-distilled knowledge to check redundancy."""
    if not DISTILLED_PATH.exists():
        return "(no existing distilled knowledge yet)"
    lines = DISTILLED_PATH.read_text(encoding="utf-8").splitlines()
    # Return the most recent entries — tail of the file
    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    return "\n".join(tail)


def _archive(raw_content: str, source_hint: str = "") -> Path:
    """Write raw article content to brain/articles/YYYY-MM-DD.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    article_file = ARTICLES_DIR / f"{today}.md"
    timestamp = datetime.now().strftime("%H:%M")
    separator = f"\n\n---\n\n## {timestamp}{' — ' + source_hint if source_hint else ''}\n\n"
    with open(article_file, "a", encoding="utf-8") as f:
        f.write(separator + raw_content.strip() + "\n")
    return article_file


def _append_to_distilled(entry: dict) -> None:
    """Append a distilled entry to brain/distilled.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")
    tags_str = ", ".join(entry.get("tags", []))
    # Use .get with defaults (like the rest of the module) — a model response
    # missing any key must not KeyError here and be reported as a distillation
    # failure after the entry already passed the score/redundancy bar.
    claim = entry.get("claim", "")
    block = (
        f"\n## {today} {timestamp} — {claim[:80]}\n"
        f"**Score:** {entry.get('score', 0)}/5  |  **Tags:** {tags_str}\n\n"
        f"**Claim:** {claim}\n\n"
        f"**Rule:** {entry.get('rule', '')}\n\n"
        f"**Why practical:** {entry.get('why_practical', '')}\n"
    )
    with open(DISTILLED_PATH, "a", encoding="utf-8") as f:
        f.write(block)


# ── Distillation prompt ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are a knowledge distiller for an elite AI product engineering team.
You read articles, tweets, threads, and screenshots and extract only what is genuinely useful in practice.

Be ruthless. Most content is noise. Your job is to find signal.

Respond ONLY with a valid JSON object — no prose, no markdown fences."""

def _build_user_prompt(existing_knowledge: str) -> str:
    return f"""Analyze the content above and return a JSON object with these fields:

- "claim": string — the single most important idea in 1-2 sentences. Be specific, not vague.
- "score": integer 1-5 — practical value score:
    1 = pure theory / academic / no application
    2 = interesting idea, hard to apply
    3 = applicable but requires significant effort or context
    4 = directly actionable with moderate effort
    5 = immediately applicable, high leverage
- "tags": array of strings — 1-4 domain tags from: [ai-agents, product, design, architecture, engineering, business, marketing, ux, performance, security, devops, research, other]
- "rule": string — a one-line actionable rule that captures the practical takeaway. Start with a verb. Leave empty string "" if score < 3.
- "why_practical": string — one sentence explaining what makes this practically useful (or why it's not, if score < 3).
- "redundant": boolean — true if this idea is already well-covered in the existing knowledge below. Don't file duplicates.
- "file": boolean — true if score >= 3 AND redundant is false. This is what gets saved to the knowledge base.
- "skip_reason": string — if file is false, brief reason why (too theoretical / already known / etc). Empty string if filing.

Existing distilled knowledge (for redundancy check — last 80 lines):
---
{existing_knowledge}
---

Return only the JSON. No explanation, no markdown, no preamble."""


# ── Core distillation ─────────────────────────────────────────────────

def _call_claude(messages: list) -> dict:
    """Call Claude API and parse JSON response."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if Claude wraps despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def distill_text(text: str, source_hint: str = "") -> dict:
    """Distill an article from pasted text.

    Returns:
        {
            "filed": bool,
            "score": int,
            "summary": str,   # short human-readable recap
            "rule": str,
            "tags": list[str],
            "skip_reason": str,
        }
    """
    existing = _load_existing_knowledge()
    messages = [
        {
            "role": "user",
            "content": f"Article content:\n\n{text}\n\n{_build_user_prompt(existing)}"
        }
    ]
    return _process_distillation(messages, raw_content=text, source_hint=source_hint)


def distill_image(image_bytes: bytes, mime_type: str = "image/jpeg",
                  source_hint: str = "") -> dict:
    """Distill an article from a screenshot image.

    Returns same shape as distill_text().
    """
    existing = _load_existing_knowledge()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": _build_user_prompt(existing),
                },
            ],
        }
    ]
    raw_content = f"[Screenshot — {source_hint or 'image'}]"
    return _process_distillation(messages, raw_content=raw_content, source_hint=source_hint)


def _process_distillation(messages: list, raw_content: str, source_hint: str) -> dict:
    """Shared post-processing after Claude responds."""
    try:
        entry = _call_claude(messages)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s", e)
        _archive(raw_content, source_hint)
        return {
            "filed": False,
            "score": 0,
            "summary": "Parse error — archived raw content.",
            "rule": "",
            "tags": [],
            "skip_reason": "JSON parse error from Claude response.",
        }
    except Exception as e:
        logger.error("Claude API call failed: %s", e)
        _archive(raw_content, source_hint)
        return {
            "filed": False,
            "score": 0,
            "summary": "API error — archived raw content.",
            "rule": "",
            "tags": [],
            "skip_reason": str(e),
        }

    # Always archive raw
    _archive(raw_content, source_hint)

    # File to distilled.md if it passes the bar
    filed = bool(entry.get("file", False))
    if filed:
        _append_to_distilled(entry)

    summary_parts = [entry.get("claim", "")]
    if entry.get("rule"):
        summary_parts.append(f"Rule: {entry['rule']}")

    return {
        "filed": filed,
        "score": entry.get("score", 0),
        "summary": "\n".join(summary_parts),
        "rule": entry.get("rule", ""),
        "tags": entry.get("tags", []),
        "skip_reason": entry.get("skip_reason", ""),
        "why_practical": entry.get("why_practical", ""),
    }
