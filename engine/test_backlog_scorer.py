#!/usr/bin/env python3
"""Tests for backlog_scorer — auto-sort tasks by North Star alignment."""
import pytest
from backlog_scorer import score_backlog_items


NORTH_STAR = """
## The Four Pillars
### 1. Farmer Accessibility
voice, WhatsApp, literacy
### 2. Actionable Intelligence
NDVI, soil, health score, treatment, API endpoints
### 3. Regenerative Impact
soil health, organic, ancestral methods, regenerative
### 4. Data Pipeline Depth
drone, NDVI, thermal, soil, weather, voice transcription
"""


def test_score_high_alignment():
    """Task mentioning multiple North Star keywords scores higher."""
    items = [
        "Add NDVI health scoring with soil analysis and treatment recommendations",
    ]
    results = score_backlog_items(items, NORTH_STAR)
    assert len(results) == 1
    assert results[0]["score"] > 0
    assert results[0]["item"] == items[0]
    # Multiple keyword hits → score at least 3
    assert results[0]["score"] >= 3


def test_score_low_alignment():
    """Task with no North Star keywords scores zero."""
    items = [
        "Refactor the logging module to use structured JSON",
    ]
    results = score_backlog_items(items, NORTH_STAR)
    assert len(results) == 1
    assert results[0]["score"] == 0


def test_score_sorts_descending():
    """Results are sorted by score, highest first."""
    items = [
        "Refactor the logging module to use structured JSON",
        "Add WhatsApp voice integration for farmer accessibility",
        "Add NDVI health scoring with soil analysis and treatment recommendations",
    ]
    results = score_backlog_items(items, NORTH_STAR)
    assert len(results) == 3
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    # The NDVI+soil+treatment task should be first or tied for first
    assert results[0]["score"] > results[-1]["score"]
