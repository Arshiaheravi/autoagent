"""Tests for knowledge_compiler.py — wiki compilation from raw session data."""
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from knowledge_compiler import (
    _parse_articles,
    _count_articles,
    _rebuild_index,
    _wiki_path,
    collect_raw_data,
    compile_wiki,
    query_wiki,
    lint_wiki,
    CATEGORIES,
)
from registry import ProjectContext


def _make_ctx(tmp_path):
    """Build a minimal ProjectContext rooted at tmp_path.

    ProjectContext derives paths from agency_home / "projects" / name.
    We set agency_home so that project_home lands inside tmp_path.
    """
    agency_home = tmp_path / "agency"
    project_home = agency_home / "projects" / "testproj"
    project_home.mkdir(parents=True)
    mem = project_home / "memory"
    mem.mkdir()
    sf = project_home / "sessions.json"
    sf.write_text("[]", encoding="utf-8")
    return ProjectContext(
        name="testproj",
        project_root=tmp_path,
        agency_home=agency_home,
    )


# ── _parse_articles ─────────────────────────────────────────────────────────

class TestParseArticles:
    def test_single_article(self):
        text = """Some preamble text.

===ARTICLE===
category: patterns
filename: retry-logic.md
title: Retry Logic
related: error-handling.md
confidence: high
---
Retry with exponential backoff is key.
Session #99 introduced this.
===END===
"""
        articles = _parse_articles(text)
        assert len(articles) == 1
        a = articles[0]
        assert a["category"] == "patterns"
        assert a["filename"] == "retry-logic.md"
        assert a["title"] == "Retry Logic"
        assert a["confidence"] == "high"
        assert "exponential backoff" in a["body"]

    def test_multiple_articles(self):
        text = """===ARTICLE===
category: concepts
filename: tdd.md
title: TDD Workflow
related: testing.md
confidence: high
---
Write tests first.
===END===

===ARTICLE===
category: failures
filename: deploy-fail.md
title: Deploy Failures
related: ci-cd.md
confidence: medium
---
Railway deploys failed due to missing env vars.
===END===
"""
        articles = _parse_articles(text)
        assert len(articles) == 2
        assert articles[0]["category"] == "concepts"
        assert articles[1]["category"] == "failures"

    def test_empty_body_skipped(self):
        text = """===ARTICLE===
category: concepts
filename: empty.md
title: Empty
confidence: low
---
===END===
"""
        articles = _parse_articles(text)
        assert len(articles) == 0

    def test_no_articles(self):
        assert _parse_articles("just some random text") == []
        assert _parse_articles("") == []

    def test_article_without_end_marker(self):
        text = """===ARTICLE===
category: techniques
filename: caching.md
title: Caching
confidence: medium
---
Cache invalidation is hard.
"""
        articles = _parse_articles(text)
        assert len(articles) == 1
        assert "Cache invalidation" in articles[0]["body"]


# ── _count_articles ─────────────────────────────────────────────────────────

class TestCountArticles:
    def test_counts_across_categories(self, tmp_path):
        wiki = tmp_path / "wiki"
        for cat in CATEGORIES:
            (wiki / cat).mkdir(parents=True)
        (wiki / "concepts" / "a.md").write_text("x")
        (wiki / "patterns" / "b.md").write_text("y")
        (wiki / "patterns" / "c.md").write_text("z")
        assert _count_articles(wiki) == 3

    def test_empty_wiki(self, tmp_path):
        wiki = tmp_path / "wiki"
        for cat in CATEGORIES:
            (wiki / cat).mkdir(parents=True)
        assert _count_articles(wiki) == 0


# ── _wiki_path ──────────────────────────────────────────────────────────────

class TestWikiPath:
    def test_creates_dirs(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        wp = _wiki_path(ctx)
        assert wp.exists()
        for cat in CATEGORIES:
            assert (wp / cat).is_dir()

    def test_idempotent(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        wp1 = _wiki_path(ctx)
        wp2 = _wiki_path(ctx)
        assert wp1 == wp2


# ── _rebuild_index ──────────────────────────────────────────────────────────

class TestRebuildIndex:
    def test_builds_index_with_articles(self, tmp_path):
        wiki = tmp_path / "wiki"
        for cat in CATEGORIES:
            (wiki / cat).mkdir(parents=True)
        (wiki / "concepts" / "auth.md").write_text(
            "---\ntitle: Auth Patterns\n---\nJWT validation is critical.", encoding="utf-8"
        )
        (wiki / "failures" / "deploy.md").write_text(
            "---\ntitle: Deploy Failures\n---\nMissing env vars cause crashes.", encoding="utf-8"
        )
        _rebuild_index(wiki)
        idx = (wiki / "_index.md").read_text(encoding="utf-8")
        assert "Auth Patterns" in idx
        assert "Deploy Failures" in idx
        assert "concepts/auth.md" in idx

    def test_empty_wiki_index(self, tmp_path):
        wiki = tmp_path / "wiki"
        for cat in CATEGORIES:
            (wiki / cat).mkdir(parents=True)
        _rebuild_index(wiki)
        idx = (wiki / "_index.md").read_text(encoding="utf-8")
        assert "Knowledge Wiki Index" in idx
        assert "Concepts" not in idx  # no articles = no category headers


# ── collect_raw_data ────────────────────────────────────────────────────────

class TestCollectRawData:
    def test_reads_knowledge_rules(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        kf = ctx.memory_dir / "knowledge.md"
        kf.write_text("RULE: [2026-01-01] Always test.\nSome other line.\nFAILED: deploy broke\n")
        raw = collect_raw_data(ctx)
        assert len(raw["knowledge_rules"]) == 2
        assert any("Always test" in r for r in raw["knowledge_rules"])
        assert any("deploy broke" in r for r in raw["knowledge_rules"])

    def test_reads_sessions(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        # Canonical schema written by session_analytics.log_session_entry:
        # key "session" (not "session_num") and nested "tests".after.
        sessions = [{"session": 1, "type": "WORK", "success": True,
                     "summary": "Built auth", "agent": "coder",
                     "tests": {"before": 0, "after": 10, "status": "pass"}}]
        ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
        raw = collect_raw_data(ctx)
        assert len(raw["session_history"]) == 1
        assert raw["session_history"][0]["num"] == 1  # not None
        assert raw["session_history"][0]["tests"] == 10

    def test_reads_activity_log(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        af = ctx.memory_dir / "activity_log.md"
        af.write_text("## 2026-05-01\nDONE: stuff\n")
        raw = collect_raw_data(ctx)
        assert "stuff" in raw.get("activity", "")

    def test_reads_security_findings(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        sf = ctx.memory_dir / "security_findings.md"
        sf.write_text("SQL injection in /api/users\n")
        raw = collect_raw_data(ctx)
        assert "SQL injection" in raw.get("security", "")

    def test_empty_project(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        raw = collect_raw_data(ctx)
        assert raw["knowledge_rules"] == []
        assert raw["session_history"] == []

    def test_malformed_sessions_json(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.sessions_file.write_text("NOT VALID JSON", encoding="utf-8")
        raw = collect_raw_data(ctx)
        assert raw["session_history"] == []


# ── compile_wiki ────────────────────────────────────────────────────────────

class TestCompileWiki:
    def test_compile_creates_articles(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        claude_output = """===ARTICLE===
category: patterns
filename: tdd-first.md
title: TDD First
related: testing.md
confidence: high
---
Always write tests before code. Session #100 confirmed this.
===END===

===ARTICLE===
category: failures
filename: timeout-bug.md
title: Timeout Bug
related: retry-logic.md
confidence: medium
---
Sessions hanging due to missing timeout. Fixed in #104.
===END===
"""
        with patch("knowledge_compiler._call_claude", return_value=claude_output):
            result = compile_wiki(ctx)
        assert result["articles_created"] == 2
        assert result["total_articles"] == 2
        wiki = ctx.memory_dir / "wiki"
        assert (wiki / "patterns" / "tdd-first.md").exists()
        assert (wiki / "failures" / "timeout-bug.md").exists()
        content = (wiki / "patterns" / "tdd-first.md").read_text(encoding="utf-8")
        assert "title: TDD First" in content
        assert "compiled_by: knowledge_compiler" in content

    def test_compile_empty_response(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with patch("knowledge_compiler._call_claude", return_value=""):
            result = compile_wiki(ctx)
        assert result["articles_created"] == 0
        assert "error" in result

    def test_compile_invalid_category_falls_back(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        claude_output = """===ARTICLE===
category: INVALID_CAT
filename: something.md
title: Something
confidence: low
---
Body text here.
===END===
"""
        with patch("knowledge_compiler._call_claude", return_value=claude_output):
            result = compile_wiki(ctx)
        assert result["articles_created"] == 1
        wiki = ctx.memory_dir / "wiki"
        assert (wiki / "concepts" / "something.md").exists()

    def test_compile_rebuilds_index(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        claude_output = """===ARTICLE===
category: techniques
filename: caching.md
title: Caching Strategy
confidence: high
---
Cache at the service layer.
===END===
"""
        with patch("knowledge_compiler._call_claude", return_value=claude_output):
            compile_wiki(ctx)
        wiki = ctx.memory_dir / "wiki"
        idx = (wiki / "_index.md").read_text(encoding="utf-8")
        assert "Caching Strategy" in idx


# ── query_wiki ──────────────────────────────────────────────────────────────

class TestQueryWiki:
    def test_query_empty_wiki(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _wiki_path(ctx)  # create dirs
        result = query_wiki(ctx, "what patterns?")
        assert "empty" in result.lower()

    def test_query_with_articles(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        wiki = _wiki_path(ctx)
        (wiki / "concepts" / "auth.md").write_text("---\ntitle: Auth\n---\nUse JWT tokens.", encoding="utf-8")
        with patch("knowledge_compiler._call_claude", return_value="Use JWT tokens for auth."):
            result = query_wiki(ctx, "how do we handle auth?")
        assert "JWT" in result


# ── lint_wiki ───────────────────────────────────────────────────────────────

class TestLintWiki:
    def test_lint_empty_wiki(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _wiki_path(ctx)
        result = lint_wiki(ctx)
        assert "empty" in result.lower()

    def test_lint_with_articles(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        wiki = _wiki_path(ctx)
        (wiki / "patterns" / "retry.md").write_text("---\ntitle: Retry\n---\nRetry with backoff.", encoding="utf-8")
        with patch("knowledge_compiler._call_claude", return_value="Wiki looks good. Consider adding error handling article."):
            result = lint_wiki(ctx)
        assert "good" in result.lower() or "Consider" in result
