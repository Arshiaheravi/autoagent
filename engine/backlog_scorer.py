#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backlog priority scorer — auto-sort tasks by North Star alignment.

Pure function: takes backlog items + North Star text, returns scored + sorted list.
No side effects, no file I/O.
"""
import re


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lowercase words (3+ chars) from text."""
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    # Filter common stop words
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was",
        "has", "have", "been", "will", "can", "not", "but", "all", "each",
        "how", "its", "what", "when", "where", "which", "who", "why",
        "add", "new", "use", "get", "set", "run", "one", "two", "test",
        "make", "more", "than", "also", "into", "just", "over", "such",
    }
    return {w for w in words if w not in stop}


def score_backlog_items(items: list[str], north_star_text: str) -> list[dict]:
    """Score backlog items by keyword overlap with North Star text.

    Args:
        items: List of backlog task descriptions (strings).
        north_star_text: The North Star document text.

    Returns:
        List of {"item": str, "score": int, "matches": list[str]}
        sorted by score descending.
    """
    ns_keywords = _extract_keywords(north_star_text)

    results = []
    for item in items:
        item_keywords = _extract_keywords(item)
        matches = sorted(item_keywords & ns_keywords)
        results.append({
            "item": item,
            "score": len(matches),
            "matches": matches,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
