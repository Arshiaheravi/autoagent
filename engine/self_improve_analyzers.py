#!/usr/bin/env python3
"""Self-improvement analysis functions — extracted from self_improve.py.

Pure analysis/utility functions:
1. share_knowledge_across_projects — cross-project rule sharing
2. inject_production_metrics — production feedback loop
3. generate_skill_from_knowledge — skill generation from experience
4. quality_gate_check — before/after test comparison
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from registry import ProjectContext, list_projects, get

logger = logging.getLogger(__name__)


def cross_project_sharing_enabled() -> bool:
    """Whether learned rules / security findings may flow BETWEEN projects.

    Off by default. In a multi-tenant deployment every project is a separate
    tenant, so copying one client's knowledge.md rules into another's is a
    cross-tenant data bleed. Enable only for a single-owner fleet via
    AUTOAGENT_CROSS_PROJECT_SHARING=1. Re-read per call so tests can toggle."""
    return os.environ.get("AUTOAGENT_CROSS_PROJECT_SHARING", "").lower() in ("1", "true", "yes", "on")


# ══════════════════════════════════════════════════════════════════
# 1. CROSS-PROJECT KNOWLEDGE SHARING
# ══════════════════════════════════════════════════════════════════

def share_knowledge_across_projects() -> int:
    """Scan all projects' knowledge.md for universal rules and copy to others.

    A rule is "universal" if it:
      - Starts with "RULE:" and doesn't mention a project-specific file path
      - Contains patterns like "always", "never", "before committing"

    Returns count of rules shared.
    """
    # Tenant isolation: never bleed rules between projects unless explicitly
    # opted in (single-owner fleet). See cross_project_sharing_enabled().
    if not cross_project_sharing_enabled():
        return 0
    projects = list_projects()
    if len(projects) < 2:
        return 0

    # Collect rules from all projects
    all_rules: dict[str, list[str]] = {}  # project_name → rules
    for p in projects:
        try:
            ctx = get(p["name"])
            kf = ctx.memory_dir / "knowledge.md"
            if not kf.exists():
                continue
            rules = []
            for line in kf.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("RULE:"):
                    rules.append(stripped)
            all_rules[p["name"]] = rules
        except Exception:
            continue

    # Find universal rules (appear in 2+ projects OR contain universal keywords)
    universal_keywords = ["before committing", "always run", "never push", "tests pass",
                          "git status", "pre-push", "constraint", "import", "before merge"]
    rule_counts: dict[str, int] = {}
    for name, rules in all_rules.items():
        for rule in rules:
            # Normalize for dedup
            key = rule.lower().strip()
            rule_counts[key] = rule_counts.get(key, 0) + 1

    # Rules in 2+ projects are universal
    universal = {k for k, v in rule_counts.items() if v >= 2}
    # Also include rules with universal keywords
    for name, rules in all_rules.items():
        for rule in rules:
            if any(kw in rule.lower() for kw in universal_keywords):
                universal.add(rule.lower().strip())

    # Share to projects that don't have them
    shared = 0
    for p in projects:
        try:
            ctx = get(p["name"])
            kf = ctx.memory_dir / "knowledge.md"
            existing = set()
            if kf.exists():
                existing = {line.strip().lower() for line in kf.read_text(encoding="utf-8").splitlines()}

            new_rules = []
            for rule_key in universal:
                if rule_key not in existing:
                    # Find the original cased version
                    original = rule_key
                    for name2, rules2 in all_rules.items():
                        for r in rules2:
                            if r.lower().strip() == rule_key:
                                original = r
                                break
                    new_rules.append(original)

            if new_rules:
                with open(kf, "a", encoding="utf-8") as f:
                    f.write(f"\n\n# Shared from other projects ({datetime.now().strftime('%Y-%m-%d')})\n")
                    for r in new_rules[:10]:  # cap at 10 to avoid bloat
                        f.write(f"{r}\n")
                shared += len(new_rules)
                logger.info("Shared %d rules to %s", len(new_rules), p["name"])
        except Exception:
            continue

    return shared


# ══════════════════════════════════════════════════════════════════
# 1b. CROSS-PROJECT SECURITY FINDING SHARING
# ══════════════════════════════════════════════════════════════════

def share_security_findings_across_projects() -> int:
    """Scan all projects' knowledge.md for security findings and share to others.

    A finding is "security-relevant" if it contains [SECURITY] tag or
    security keywords (injection, XSS, auth bypass, SSRF, secret, vulnerability).

    Returns count of findings shared.
    """
    # Tenant isolation: gated with the same opt-in as rule sharing.
    if not cross_project_sharing_enabled():
        return 0
    projects = list_projects()
    if len(projects) < 2:
        return 0

    security_keywords = [
        "[security]", "injection", "xss", "ssrf", "auth bypass",
        "vulnerability", "secret leak", "csrf", "rce", "path traversal",
        "privilege escalation", "insecure deserialization",
    ]

    # Collect security findings from all projects
    all_findings: dict[str, list[str]] = {}  # project_name → findings
    for p in projects:
        try:
            ctx = get(p["name"])
            kf = ctx.memory_dir / "knowledge.md"
            if not kf.exists():
                continue
            findings = []
            for line in kf.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith("RULE:"):
                    continue
                if any(kw in stripped.lower() for kw in security_keywords):
                    findings.append(stripped)
            all_findings[p["name"]] = findings
        except Exception:
            continue

    # Share findings to projects that don't have them
    shared = 0
    for p in projects:
        try:
            ctx = get(p["name"])
            kf = ctx.memory_dir / "knowledge.md"
            existing = set()
            if kf.exists():
                existing = {line.strip().lower() for line in kf.read_text(encoding="utf-8").splitlines()}

            new_findings = []
            for source_name, findings in all_findings.items():
                if source_name == p["name"]:
                    continue  # Don't share back to the source
                for finding in findings:
                    if finding.lower().strip() not in existing:
                        new_findings.append(finding)

            if new_findings:
                with open(kf, "a", encoding="utf-8") as f:
                    f.write(f"\n\n# Security findings from other projects ({datetime.now().strftime('%Y-%m-%d')})\n")
                    for finding in new_findings[:20]:  # cap to avoid bloat
                        f.write(f"{finding}\n")
                shared += len(new_findings)
                logger.info("Shared %d security findings to %s", len(new_findings), p["name"])
        except Exception:
            continue

    return shared


# ══════════════════════════════════════════════════════════════════
# 2. PRODUCTION FEEDBACK LOOP
# ══════════════════════════════════════════════════════════════════

def inject_production_metrics(ctx: ProjectContext) -> str:
    """Read production metrics and inject into backlog priority.

    Reads sessions.json for success rates and test counts.

    Returns summary string injected into knowledge.md.
    """
    if not ctx.sessions_file.exists():
        return ""

    try:
        sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return ""

    if not sessions:
        return ""

    # Extract metrics from last 10 sessions
    recent = sessions[-10:]
    success_rate = sum(1 for s in recent if s.get("success") or s.get("quality", {}).get("score", 0) > 50) / len(recent)
    test_counts = []
    for s in recent:
        # Test count lives in the nested `tests` dict (tests.after), NOT under
        # `quality` — the quality dict only carries `score`. Reading
        # quality.tests_after always yielded 0, so this metric was stuck at 0.
        t = s.get("tests") or {}
        tc = t.get("after", 0) if isinstance(t, dict) else 0
        if not isinstance(tc, (int, float)):
            tc = 0
        test_counts.append(tc)
    avg_tests = sum(test_counts) / len(test_counts) if test_counts else 0

    summary = (
        f"METRIC: [{datetime.now().strftime('%Y-%m-%d')}] "
        f"Last 10 sessions: {success_rate:.0%} success, {avg_tests:.0f} avg tests. "
    )

    # Inject into knowledge.md
    kf = ctx.memory_dir / "knowledge.md"
    if kf.exists():
        content = kf.read_text(encoding="utf-8")
        # Remove old metrics (keep only latest)
        lines = [l for l in content.splitlines() if not l.startswith("METRIC:")]
        lines.append(summary)
        kf.write_text("\n".join(lines), encoding="utf-8")

    return summary


# ══════════════════════════════════════════════════════════════════
# 3. SKILL GENERATION FROM EXPERIENCE
# ══════════════════════════════════════════════════════════════════

def generate_skill_from_knowledge(ctx: ProjectContext) -> Optional[str]:
    """Scan knowledge.md for repeated patterns and generate a new skill .md.

    If 3+ rules mention the same topic (e.g., "frontend page"), create a
    skill file that codifies the pattern.

    Returns skill filename if created, None otherwise.
    """
    kf = ctx.memory_dir / "knowledge.md"
    if not kf.exists():
        return None

    rules = []
    for line in kf.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("RULE:") or line.strip().startswith("SKILL:"):
            rules.append(line.strip())

    if len(rules) < 5:
        return None

    # Count topic keywords in rules
    topic_counts: dict[str, list[str]] = {}
    topic_keywords = {
        "frontend-page": ["page loads", "frontend", "html", ".js file", "renders"],
        "api-endpoint": ["endpoint", "route", "POST", "GET", "api/"],
        "database": ["migration", "column", "ALTER TABLE", "model", "db"],
        "testing": ["test_", "pytest", "assert", "fixture", "conftest"],
    }

    for topic, keywords in topic_keywords.items():
        matching = [r for r in rules if any(kw.lower() in r.lower() for kw in keywords)]
        if len(matching) >= 3:
            topic_counts[topic] = matching

    # Generate skill for the most common topic
    if not topic_counts:
        return None

    top_topic = max(topic_counts, key=lambda k: len(topic_counts[k]))
    matching_rules = topic_counts[top_topic]

    # Check if skill already exists
    skills_dir = ctx.project_home / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skills_dir / f"{top_topic}.md"
    if skill_file.exists():
        return None  # Already generated

    # Generate the skill file
    content = f"# {top_topic.replace('-', ' ').title()}\n\n"
    content += f"Auto-generated from {len(matching_rules)} knowledge rules.\n\n"
    content += "## Pattern\n\n"
    for rule in matching_rules[:5]:
        content += f"- {rule}\n"
    content += "\n## Checklist\n\n"
    content += "1. Read the relevant existing files before making changes\n"
    content += "2. Follow TDD — write failing tests first\n"
    content += "3. Verify all tests pass before committing\n"

    skill_file.write_text(content, encoding="utf-8")
    logger.info("Generated skill %s for %s from %d rules", top_topic, ctx.name, len(matching_rules))
    return top_topic


# ══════════════════════════════════════════════════════════════════
# 4. QUALITY GATE ON SELF-EDITS
# ══════════════════════════════════════════════════════════════════

def quality_gate_check(ctx: ProjectContext) -> dict:
    """Compare test count before and after last session.

    If test count dropped or tests started failing, flag the session
    as potentially harmful and log a warning to knowledge.md.

    Returns: {"ok": bool, "tests_before": int, "tests_after": int, "delta": int}
    """
    if not ctx.sessions_file.exists():
        return {"ok": True, "tests_before": 0, "tests_after": 0, "delta": 0}

    try:
        sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": True, "tests_before": 0, "tests_after": 0, "delta": 0}

    if len(sessions) < 2:
        return {"ok": True, "tests_before": 0, "tests_after": 0, "delta": 0}

    prev = sessions[-2]
    curr = sessions[-1]

    prev_q = prev.get("quality", {})
    curr_q = curr.get("quality", {})
    tests_before = (prev_q.get("tests_after", 0) if isinstance(prev_q, dict) else 0) or 0
    tests_after = (curr_q.get("tests_after", 0) if isinstance(curr_q, dict) else 0) or 0
    if not isinstance(tests_before, (int, float)):
        tests_before = 0
    if not isinstance(tests_after, (int, float)):
        tests_after = 0
    delta = tests_after - tests_before

    ok = delta >= 0  # Tests should never decrease

    if not ok:
        # Log warning
        kf = ctx.memory_dir / "knowledge.md"
        warning = (
            f"\nRULE: [QUALITY GATE] Session #{curr.get('session', '?')} — "
            f"TEST COUNT DROPPED from {tests_before} to {tests_after} ({delta}). "
            f"Investigate: tests may have been deleted or broken.\n"
        )
        if kf.exists():
            kf.write_text(kf.read_text(encoding="utf-8") + warning, encoding="utf-8")
        logger.warning("Quality gate FAILED for %s: tests dropped %d → %d", ctx.name, tests_before, tests_after)

    return {"ok": ok, "tests_before": tests_before, "tests_after": tests_after, "delta": delta}
