#!/usr/bin/env python3
"""Knowledge Compiler — structured wiki from raw session data.

Inspired by Karpathy's LLM knowledge base pattern:
raw data → compiled wiki → Q&A → enhanced wiki

Instead of append-only knowledge.md, this compiles structured articles
organized by topic, with backlinks, summaries, and indexes.

Wiki structure:
  .autoagent/wiki/
    _index.md          — master index with all articles + summaries
    _stats.md          — compilation stats (articles, sources, last compiled)
    concepts/          — core concept articles (e.g., "auth-patterns.md")
    patterns/          — recurring patterns (e.g., "n-plus-one-queries.md")
    failures/          — failure postmortems (e.g., "railway-deploy-failures.md")
    decisions/         — architectural decisions (e.g., "chose-sse-over-websocket.md")
    techniques/        — learned techniques (e.g., "playwright-screenshot-testing.md")

Each article has frontmatter:
  ---
  title: Auth Patterns
  category: concepts
  sources: [session #42, session #67, knowledge.md rule 12]
  related: [jwt-validation, cors-misconfig, rate-limiting]
  confidence: high
  last_updated: 2026-04-02
  ---
"""
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from registry import ProjectContext

logger = logging.getLogger(__name__)

WIKI_DIR = "wiki"
CATEGORIES = ["concepts", "patterns", "failures", "decisions", "techniques"]


def _wiki_path(ctx: ProjectContext) -> Path:
    """Get the wiki directory for a project."""
    p = ctx.memory_dir / WIKI_DIR
    p.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (p / cat).mkdir(exist_ok=True)
    return p


def _find_claude() -> str:
    return shutil.which("claude") or "claude"


def _call_claude(prompt: str, cwd: str, timeout: int = 180, max_turns: int = 1) -> str:
    """Call Claude CLI for knowledge compilation."""
    try:
        result = subprocess.run(
            [_find_claude(), "-p", prompt, "--max-turns", str(max_turns), "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
            cwd=cwd, encoding="utf-8", errors="replace",
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        logger.warning("Claude call failed: %s", e)
        return ""


# ── Raw Data Collection ──────────────────────────────────────────────────────

def collect_raw_data(ctx: ProjectContext) -> dict:
    """Collect all raw data sources for compilation."""
    raw = {"knowledge_rules": [], "session_history": [], "failures": [], "decisions": []}

    # Knowledge rules
    kf = ctx.memory_dir / "knowledge.md"
    if kf.exists():
        content = kf.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("RULE:") or stripped.startswith("ACCOMPLISHED:") or stripped.startswith("FAILED:"):
                raw["knowledge_rules"].append(stripped)

    # Session history
    sf = ctx.sessions_file
    if sf.exists():
        try:
            sessions = json.loads(sf.read_text(encoding="utf-8"))
            for s in sessions[-50:]:  # last 50 sessions
                raw["session_history"].append({
                    # Canonical keys are "session" and nested "tests".after —
                    # not "session_num"/"tests_after". The old keys made every
                    # num None (→ "#None" fed to the wiki-compile prompt).
                    "num": s.get("session"),
                    "type": s.get("type"),
                    "success": s.get("success"),
                    "summary": s.get("summary", ""),
                    "agent": s.get("agent"),
                    "tests": (s.get("tests") or {}).get("after", 0),
                })
        except Exception:
            pass

    # Activity log
    af = ctx.memory_dir / "activity_log.md"
    if af.exists():
        raw["activity"] = af.read_text(encoding="utf-8")[-3000:]

    # Security findings
    sec = ctx.memory_dir / "security_findings.md"
    if sec.exists():
        raw["security"] = sec.read_text(encoding="utf-8")

    return raw


# ── Compilation ──────────────────────────────────────────────────────────────

def compile_wiki(ctx: ProjectContext) -> dict:
    """Compile raw data into structured wiki articles.

    Uses Claude to:
    1. Extract topics from raw data
    2. Generate/update articles per topic
    3. Build backlinks and index
    """
    wiki = _wiki_path(ctx)
    raw = collect_raw_data(ctx)

    # Build compilation prompt
    rules_text = "\n".join(raw["knowledge_rules"][-30:])
    sessions_text = "\n".join(
        f"#{s['num']} [{s['type']}] {'OK' if s['success'] else 'FAIL'} agent={s.get('agent') or '-'} {s.get('summary','')[:60]}"
        for s in raw["session_history"][-20:]
    )

    prompt = f"""You are a knowledge compiler for project '{ctx.name}'.

From these raw data sources, generate structured wiki articles.

## Raw Knowledge Rules (last 30)
{rules_text}

## Recent Sessions (last 20)
{sessions_text}

## Instructions
Analyze the data and output 3-8 wiki articles in this EXACT format (repeat for each article):

===ARTICLE===
category: [concepts|patterns|failures|decisions|techniques]
filename: [kebab-case-name.md]
title: [Human Readable Title]
related: [comma-separated related article filenames]
confidence: [high|medium|low]
---
[Article body in markdown, 100-300 words. Include specific examples from the data.
Reference session numbers. Be concrete, not generic.]
===END===

Focus on:
- Recurring patterns (what keeps working/failing)
- Key decisions made and why
- Techniques that improved quality
- Failure patterns to avoid
- Core concepts the project relies on"""

    output = _call_claude(prompt, str(ctx.project_root))
    if not output:
        return {"articles_created": 0, "error": "Claude returned empty response"}

    # Parse articles from output
    articles = _parse_articles(output)
    written = 0

    for article in articles:
        cat = article.get("category", "concepts")
        if cat not in CATEGORIES:
            cat = "concepts"
        filename = article.get("filename", "untitled.md")
        filepath = wiki / cat / filename

        # Build frontmatter
        frontmatter = (
            f"---\n"
            f"title: {article.get('title', filename)}\n"
            f"category: {cat}\n"
            f"related: [{article.get('related', '')}]\n"
            f"confidence: {article.get('confidence', 'medium')}\n"
            f"last_updated: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"compiled_by: knowledge_compiler\n"
            f"---\n\n"
        )

        filepath.write_text(frontmatter + article.get("body", ""), encoding="utf-8")
        written += 1
        logger.info("Wiki article: %s/%s", cat, filename)

    # Rebuild index
    _rebuild_index(wiki)

    return {"articles_created": written, "total_articles": _count_articles(wiki)}


def _parse_articles(text: str) -> list[dict]:
    """Parse ===ARTICLE=== blocks from Claude output."""
    articles = []
    blocks = re.split(r'===ARTICLE===', text)

    for block in blocks[1:]:  # skip preamble
        block = block.split("===END===")[0].strip()
        article = {}

        # Parse header fields
        lines = block.splitlines()
        body_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "---":
                body_start = i + 1
                break
            if ":" in line:
                key, val = line.split(":", 1)
                article[key.strip().lower()] = val.strip()

        article["body"] = "\n".join(lines[body_start:]).strip()
        if article.get("body"):
            articles.append(article)

    return articles


def _rebuild_index(wiki: Path):
    """Rebuild the master _index.md with all articles."""
    lines = ["# Knowledge Wiki Index\n", f"_Last compiled: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]

    for cat in CATEGORIES:
        cat_dir = wiki / cat
        articles = sorted(cat_dir.glob("*.md"))
        if not articles:
            continue
        lines.append(f"\n## {cat.title()}\n")
        for a in articles:
            content = a.read_text(encoding="utf-8")
            # Extract title from frontmatter
            title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else a.stem.replace("-", " ").title()
            # First non-frontmatter line as summary
            body = content.split("---")[-1].strip() if "---" in content else content
            summary = body.splitlines()[0][:100] if body else ""
            lines.append(f"- [{title}]({cat}/{a.name}) — {summary}")

    (wiki / "_index.md").write_text("\n".join(lines), encoding="utf-8")


def _count_articles(wiki: Path) -> int:
    """Count total wiki articles."""
    return sum(1 for cat in CATEGORIES for _ in (wiki / cat).glob("*.md"))


# ── Query ────────────────────────────────────────────────────────────────────

def query_wiki(ctx: ProjectContext, question: str) -> str:
    """Ask a question against the compiled wiki."""
    wiki = _wiki_path(ctx)
    index = wiki / "_index.md"

    # Collect all articles (limited to fit context)
    articles_text = ""
    for cat in CATEGORIES:
        for f in sorted((wiki / cat).glob("*.md")):
            content = f.read_text(encoding="utf-8")
            articles_text += f"\n\n## [{cat}/{f.name}]\n{content[:500]}"
            if len(articles_text) > 8000:
                break

    if not articles_text:
        return "Wiki is empty. Run compile_wiki() first."

    prompt = f"""You are answering questions about the '{ctx.name}' project knowledge base.

## Wiki Articles
{articles_text}

## Question
{question}

Answer concisely using the wiki data. Reference specific articles. If the answer isn't in the wiki, say so."""

    return _call_claude(prompt, str(ctx.project_root), max_turns=2)


# ── Health Check (Linting) ───────────────────────────────────────────────────

def lint_wiki(ctx: ProjectContext) -> str:
    """Run health checks on the wiki — find gaps, inconsistencies, suggestions."""
    wiki = _wiki_path(ctx)
    articles_text = ""
    for cat in CATEGORIES:
        for f in sorted((wiki / cat).glob("*.md")):
            articles_text += f"\n[{cat}/{f.name}]: {f.read_text(encoding='utf-8')[:300]}\n"

    if not articles_text:
        return "Wiki is empty."

    prompt = f"""Review this knowledge wiki for '{ctx.name}' and identify:
1. Inconsistencies between articles
2. Missing topics that should be covered (based on what IS covered)
3. Articles that need updating (low confidence, old dates)
4. Interesting connections between articles that aren't linked
5. Suggested questions to investigate further

Wiki contents:
{articles_text[:6000]}

Output a concise health report with specific recommendations."""

    return _call_claude(prompt, str(ctx.project_root), max_turns=2)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from registry import get, list_projects

    args = sys.argv[1:]
    if not args:
        print("Usage: python knowledge_compiler.py [compile|query|lint|stats] <project> [question]")
        sys.exit(0)

    cmd = args[0]
    project = args[1] if len(args) > 1 else list_projects()[0]["name"]
    ctx = get(project)

    if cmd == "compile":
        result = compile_wiki(ctx)
        print(f"Compiled: {result['articles_created']} articles ({result.get('total_articles', 0)} total)")
    elif cmd == "query":
        question = " ".join(args[2:]) if len(args) > 2 else "What are the key patterns in this project?"
        print(query_wiki(ctx, question))
    elif cmd == "lint":
        print(lint_wiki(ctx))
    elif cmd == "stats":
        wiki = _wiki_path(ctx)
        total = _count_articles(wiki)
        print(f"Wiki: {total} articles across {len(CATEGORIES)} categories")
        for cat in CATEGORIES:
            count = len(list((wiki / cat).glob("*.md")))
            if count:
                print(f"  {cat}: {count}")
    else:
        print(f"Unknown command: {cmd}")
