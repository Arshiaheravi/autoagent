"""ADR (Architecture Decision Record) puller.

Live sources:
  - github.com/joelparkerhenderson/architecture-decision-record (curated index)
  - GitHub search: `path:adr extension:md "## Context" "## Decision"`
  - Major OSS repos with adr/ dirs: kubernetes, backstage, microservices,
    materialize, openzeppelin, npm, vercel/next.js (a few each).

Each ADR follows roughly:

    # NNNN. Title
    * Status: accepted | proposed | superseded
    * Date: YYYY-MM-DD
    ## Context ...
    ## Decision ...
    ## Consequences ...

Parser is pure (no network) so tests run offline against fixture text.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ADR_CURATED_INDEX_URL = (
    "https://github.com/joelparkerhenderson/architecture-decision-record"
)


def _extract_section(text: str, header: str) -> str:
    """Pull a `## <header>` ... up-to-next-`##-or-end` block. Case insensitive."""
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return (m.group(1) if m else "").strip()


def _extract_status(text: str) -> str:
    """Status line — `* Status: accepted` or similar."""
    m = re.search(r"^\s*[\*\-]\s*Status:\s*(.+?)\s*$",
                  text, flags=re.IGNORECASE | re.MULTILINE)
    return (m.group(1) if m else "").strip()


def _extract_title(text: str) -> str:
    """First H1 line, with leading `NNNN.` numbering stripped."""
    m = re.search(r"^#\s+(?:\d+\.\s*)?(.+?)\s*$", text, flags=re.MULTILINE)
    return (m.group(1) if m else "").strip()


def _confidence_from_status(status: str) -> str:
    s = status.lower()
    if "accepted" in s or "implemented" in s:
        return "HIGH"
    if "proposed" in s or "draft" in s:
        return "MEDIUM"
    if "superseded" in s or "deprecated" in s or "rejected" in s:
        return "LOW"
    return "MEDIUM"


_LEAD_CLAUSE = re.compile(
    r"^(we\s+(will|are\s+going\s+to|have\s+decided\s+to|decide\s+to|"
    r"choose\s+to|chose\s+to|will\s+use)\s+)"
    r"|^(let'?s\s+)"
    r"|^(decided?\s+to\s+)"
    r"|^(adopt(ing|ed|s)?\s+)"
    r"|^(use\s+)",
    flags=re.IGNORECASE,
)


def _short_winner(decision: str) -> str:
    """First sentence with leading boilerplate stripped → noun-led
    headline outcome. Council uses this as the `winner` field."""
    if not decision:
        return ""
    first = re.split(r"[.\n]", decision, maxsplit=1)[0].strip()
    # Strip leading "we will use" / "we chose" / "let's" / etc.
    while True:
        stripped = _LEAD_CLAUSE.sub("", first).strip()
        if stripped == first:
            break
        first = stripped
    return first[:120]


def parse_adr_markdown(text: str, *, repo: str, path: str) -> Optional[dict]:
    """Parse one ADR markdown file → canonical council-corpus row.
    Returns None if the file doesn't carry Context + Decision sections."""
    context = _extract_section(text, "Context")
    decision = _extract_section(text, "Decision")
    if not context.strip() or not decision.strip():
        return None

    title = _extract_title(text) or path
    status = _extract_status(text)
    consequences = _extract_section(text, "Consequences")

    body_synthesis = decision
    if consequences:
        body_synthesis += "\n\nConsequences:\n" + consequences

    return {
        "id":          f"{repo}::{path}",
        "title":       title,
        "question":    context,
        "synthesis":   body_synthesis,
        "winner":      _short_winner(decision),
        "confidence":  _confidence_from_status(status),
        "platform":    "adrs",
        "context":     f"{repo} {path}",
        "decided_at":  "",  # could parse `* Date:` if present
        "url":         f"https://github.com/{repo}/blob/HEAD/{path}",
    }


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    """Pull ADRs from public GitHub repos and write canonical JSON.

    Default strategy: walk a list of known-good repos, fetch each adr/
    or docs/adr/ directory via GitHub API, parse each .md file.
    Implement when the live pull becomes needed — fixture-based parser
    is sufficient for now (tested via parse_adr_markdown directly).
    """
    raise NotImplementedError(
        f"pull_adrs live fetch — implement against {ADR_CURATED_INDEX_URL}. "
        "Curate a target-repos.json list, walk each repo's adr/ dir, parse "
        "each .md with parse_adr_markdown. Skip when fixture-based tests "
        "and ad-hoc local-path ingestion are sufficient."
    )


__all__ = [
    "parse_adr_markdown",
    "pull",
    "ADR_CURATED_INDEX_URL",
]
