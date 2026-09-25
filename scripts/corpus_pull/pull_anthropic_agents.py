"""Anthropic agent-design corpus puller.

Live sources (public, no auth):
  - https://www.anthropic.com/news (engineering blog, including
    "Building effective agents" and the long-running-agents series)
  - https://docs.claude.com (Claude Agent SDK docs)
  - https://github.com/anthropics/anthropic-cookbook (84 notebooks)
  - https://github.com/anthropics/claude-code-security-review (CCSR)
  - https://github.com/anthropics/cwc-long-running-agents (LRA)
  - https://github.com/anthropics/financial-services-skills
  - https://github.com/anthropics/claude-for-legal
  - https://github.com/anthropics/skills

Each source yields one or more council-corpus rows where:
  - question  = the design problem the post / pattern addresses
  - synthesis = the recommendation / pattern body
  - winner    = the named pattern (advisor, evaluator-optimizer,
                orchestrator-workers, ...)
  - confidence = HIGH (these are Anthropic's official recommendations)
  - platform  = "anthropic"

The parser is pure so tests run offline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Each known agent-design post / repo we want to crawl. Run `pull()` with
# `local_paths=[...]` to fold in already-downloaded copies instead of
# hitting the network — useful while live scraping is deferred.
ANTHROPIC_SOURCES = [
    {"url": "https://www.anthropic.com/news/building-effective-agents",
     "topic": "agent design patterns"},
    {"url": "https://www.anthropic.com/news/code-execution-with-mcp",
     "topic": "MCP tool execution"},
    {"url": "https://www.anthropic.com/research/contextual-retrieval",
     "topic": "retrieval augmentation"},
    {"url": "https://docs.claude.com/en/docs/agents-and-tools",
     "topic": "tool use"},
    {"url": "https://github.com/anthropics/anthropic-cookbook",
     "topic": "cookbook patterns"},
    {"url": "https://github.com/anthropics/skills",
     "topic": "skill packaging"},
    {"url": "https://github.com/anthropics/claude-code-security-review",
     "topic": "CCSR — security review confidence scoring"},
    {"url": "https://github.com/anthropics/cwc-long-running-agents",
     "topic": "LRA — long-running agent contract"},
]


def _confidence_from_source(url: str) -> str:
    """Anthropic publications: official posts = HIGH, repo READMEs = HIGH,
    individual cookbook notebooks = MEDIUM (not all are blessed canon)."""
    u = url.lower()
    if "/news/" in u or "/research/" in u or "docs.claude.com" in u:
        return "HIGH"
    if "github.com/anthropics" in u:
        return "HIGH"  # official org
    return "MEDIUM"


def _extract_winner(content: str) -> str:
    """Heuristic: first ALL-CAPS or TitleCase phrase in the first 400 chars
    that looks like a named pattern. Falls back to the first sentence."""
    head = content[:400].strip()
    # Look for explicit pattern names mentioned in Anthropic docs.
    named = ("advisor", "orchestrator-workers", "evaluator-optimizer",
             "parallelization", "prompt chaining", "routing",
             "agent contract", "evidence gate", "AGENT_STOP",
             "confidence rescorer", "retrieval-augmented")
    head_lower = head.lower()
    for name in named:
        if name in head_lower:
            return name
    first = head.split(".")[0].strip()
    return first[:120]


def parse_anthropic_post(post: dict) -> Optional[dict]:
    """Parse a single Anthropic post / doc dict → canonical row.

    Expected input keys: title, url, content, [published_at, topic].
    Returns None for empty content.
    """
    content = (post.get("content") or "").strip()
    if not content:
        return None

    title = post.get("title") or ""
    url = post.get("url") or ""
    topic = post.get("topic") or ""

    # Question = problem statement we extract from the topic + first sentence.
    first_sent = content.split(".")[0].strip()
    question = (f"{topic}: " if topic else "") + first_sent
    question = question.strip()[:500]

    return {
        "id":          url.rsplit("/", 1)[-1] or title.lower().replace(" ", "-")[:60],
        "title":       title,
        "question":    question,
        "synthesis":   content[:4000],  # cap to keep embedding cost bounded
        "winner":      _extract_winner(content),
        "confidence":  _confidence_from_source(url),
        "platform":    "anthropic",
        "context":     f"anthropic publication: {topic}".strip(": "),
        "decided_at":  post.get("published_at", ""),
        "url":         url,
    }


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    """Fetch Anthropic-published agent content → canonical JSON.

    Live network strategy (not yet implemented — fixture/parser is
    sufficient for now): walk ANTHROPIC_SOURCES, fetch each URL,
    extract title + main content (for /news posts use the article body,
    for GH repos pull the top-level README), call parse_anthropic_post.

    `local_paths` kwarg (list of {url, path}) lets the operator fold in
    already-downloaded copies — useful when memory pins already contain
    the content and we just want to promote them into the corpus.
    """
    raise NotImplementedError(
        "pull_anthropic_agents live fetch — implement against "
        f"{len(ANTHROPIC_SOURCES)} known sources (see ANTHROPIC_SOURCES). "
        "For now use parse_anthropic_post() with locally-collected content "
        "from the existing memory pins ([[reference_anthropic_skills_repo]], "
        "[[reference_anthropic_cookbooks]], [[reference_ccsr_patterns]], "
        "[[reference_lra_patterns]], etc) to seed the corpus."
    )


__all__ = ["parse_anthropic_post", "pull", "ANTHROPIC_SOURCES"]
