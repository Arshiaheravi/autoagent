#!/usr/bin/env python3
"""Extended director commands — extracted from director_helpers.py.

Handles /screenshot, /graph, /flags, /council, /orchestrator, /wiki, /red commands.
"""
import sys
import subprocess
from pathlib import Path


def _resolve_project_name(name: str) -> str:
    """Resolve case-insensitive project names to their canonical registry entry."""
    from registry import list_projects
    for project in list_projects():
        if project["name"].lower() == name.lower():
            return project["name"]
    return name

def cmd_screenshot(cmd: str) -> str:
    parts = cmd.split()
    if len(parts) > 1:
        project = _resolve_project_name(parts[1])
    else:
        # Default to the first registered project — no hardcoded client name.
        from registry import list_projects
        projs = list_projects()
        if not projs:
            return "No projects registered. Usage: /screenshot <project>"
        project = projs[0]["name"]
    try:
        from visual_check import take_screenshots
        from registry import get
        from comms import send_photo
        ctx = get(project)
        results = take_screenshots(ctx, pages=["/"])
        sent = 0
        for r in results:
            if r.get("file"):
                overflow_warn = " \u26a0\ufe0f OVERFLOW" if r.get("overflow") else ""
                errors_warn = f" \u26a0\ufe0f {r['console_errors']} JS errors" if r.get("console_errors", 0) > 0 else ""
                send_photo(r["file"], f"<b>{project}</b> \u2014 {r['viewport']} ({r['width']}px){overflow_warn}{errors_warn}")
                sent += 1
        return f"\U0001f4f8 Sent {sent} screenshots for {project}."
    except Exception as e:
        return f"Screenshot failed: {e}"


def cmd_graph(cmd: str) -> str:
    parts = cmd.split()
    project = parts[1] if len(parts) > 1 else None
    if not project:
        return "Usage: /graph <project_name>"
    project = _resolve_project_name(project)
    try:
        from registry import get
        from task_graph import TaskGraph
        ctx = get(project)
        backlog = ctx.memory_dir / "backlog.md"
        if not backlog.exists():
            return f"No backlog for {project}."
        graph = TaskGraph.from_backlog(backlog.read_text(encoding="utf-8"))
        s = graph.summary()
        ready = graph.find_ready()
        ready_list = "\n".join(f"  - {t.name}" for t in ready[:5])
        return (
            f"\U0001f4ca <b>{project} Task Graph</b>\n\n"
            f"Total: {s['total']} | Done: {s['done']} | Remaining: {s['remaining']}\n"
            f"Ready: {s['ready_now']} | Blocked: {s['blocked']}\n"
            f"Parallel batches: {s['parallel_batches']}\n"
            f"Critical path: {s['critical_path_length']} steps\n\n"
            f"<b>Ready now:</b>\n{ready_list}"
        )
    except Exception as e:
        return f"Error: {e}"


def cmd_flags(cmd: str) -> str:
    parts = cmd.split()
    if len(parts) < 2:
        return "Usage: /flags <project> [flag on|off]"
    try:
        from registry import get
        from features import list_flags, set_flag
        ctx = get(_resolve_project_name(parts[1]))
        if len(parts) == 2:
            flags = list_flags(ctx)
            lines = [f"\U0001f3f4 <b>{ctx.name} Feature Flags</b>\n"]
            for name, on in flags.items():
                lines.append(f"  {'ON' if on else 'OFF'}  {name}")
            return "\n".join(lines)
        elif len(parts) >= 4:
            flag, state = parts[2], parts[3].lower()
            set_flag(ctx, flag, state in ("on", "true", "1"))
            return f"{'ON' if state in ('on','true','1') else 'OFF'}  {flag} for {ctx.name}"
        return "Usage: /flags <project> <flag> <on|off>"
    except Exception as e:
        return f"Error: {e}"


def cmd_council(cmd: str) -> str:
    question = cmd[8:].strip()
    if not question:
        return "Usage: /council <question>\n\nExample: /council Should we deploy myapp to Railway this week?"
    try:
        from council import convene_council
        result = convene_council(question)
        if "error" in result:
            return f"Council error: {result['error']}"
        perspectives = "\n".join(
            f"  <b>{r['name']}</b>: {r['response'][:120]}..."
            for r in result["stage1"]
        )
        rankings = " > ".join(
            a["name"] for a in result["stage2"]["aggregate"]
        )
        return (
            f"\U0001f3db <b>Council Result</b>\n\n"
            f"<b>Question:</b> {question[:200]}\n\n"
            f"<b>Perspectives:</b>\n{perspectives}\n\n"
            f"<b>Ranking:</b> {rankings}\n\n"
            f"<b>Synthesis:</b>\n{result['synthesis'][:800]}\n\n"
            f"Confidence: <b>{result['confidence']}</b>"
        )
    except Exception as e:
        return f"Council failed: {e}"

def cmd_wiki(cmd: str) -> str:
    parts = cmd.split(maxsplit=2)
    sub = parts[1] if len(parts) > 1 else "stats"
    try:
        from registry import get, list_projects
        from knowledge_compiler import compile_wiki, query_wiki, lint_wiki, _wiki_path, _count_articles, CATEGORIES
        project = parts[2] if len(parts) > 2 and sub in ("compile", "lint", "stats") else (parts[2].split(maxsplit=1)[0] if len(parts) > 2 else list_projects()[0]["name"])
        ctx = get(_resolve_project_name(project))
        if sub == "compile":
            result = compile_wiki(ctx)
            return f"\U0001f4da Compiled {result['articles_created']} articles for {ctx.name} ({result.get('total_articles', 0)} total)"
        elif sub == "stats":
            wiki = _wiki_path(ctx)
            total = _count_articles(wiki)
            lines = [f"\U0001f4da <b>{ctx.name} Wiki</b> \u2014 {total} articles\n"]
            for cat in CATEGORIES:
                count = len(list((wiki / cat).glob("*.md")))
                if count: lines.append(f"  {cat}: {count}")
            return "\n".join(lines) if total > 0 else f"\U0001f4da {ctx.name} wiki is empty. Run /wiki compile {ctx.name}"
        elif sub == "lint":
            return f"\U0001f4da <b>Wiki Health Check</b>\n\n{lint_wiki(ctx)[:1500]}"
        elif sub == "query":
            question = " ".join(parts[2:]) if len(parts) > 2 else "What are the key patterns?"
            return f"\U0001f4da {query_wiki(ctx, question)[:1500]}"
        return "Usage: /wiki [compile|stats|lint|query] [project] [question]"
    except Exception as e:
        return f"Wiki error: {e}"


def cmd_red(cmd: str) -> str:
    parts = cmd.split()
    sub = parts[1] if len(parts) > 1 else "status"
    try:
        from red_bridge import get_bridge_stats, get_unverified_findings, sync_findings
        if sub == "status":
            s = get_bridge_stats()
            return (f"\U0001f534 <b>Red Team Status</b>\n\n"
                f"Findings: {s['total_findings']} total, {s['verified']} fixed, {s['pending']} pending\n"
                f"By severity: {', '.join(f'{k}: {v}' for k, v in s['by_severity'].items())}")
        elif sub == "findings":
            findings = get_unverified_findings()
            if not findings:
                return "\U0001f534 No pending findings \u2014 all clear."
            lines = ["\U0001f534 <b>Pending Red Findings</b>\n"]
            for f in findings[:10]:
                lines.append(f"  [{f['severity'].upper()}] {f['task_id']} \u2014 {f['vuln_type']} ({f['project']})")
            return "\n".join(lines)
        elif sub == "sync":
            from registry import list_projects, get
            total = 0
            for p in list_projects():
                ctx = get(p["name"])
                new = sync_findings(ctx)
                total += len(new)
            return f"\U0001f534 Synced {total} new findings \u2192 Build backlogs."
        elif sub == "triage":
            finding_id = parts[2] if len(parts) > 2 else None
            if not finding_id:
                return "Usage: /red triage <finding_id>"
            from red_bridge import council_triage
            finding = {"finding_id": finding_id, "vuln_type": "unknown", "severity": "medium", "endpoint": "unknown", "evidence": ""}
            unverified = get_unverified_findings()
            for f in unverified:
                if str(f.get("finding_id")) == str(finding_id) or f.get("task_id") == f"RED-{finding_id}":
                    finding.update({"vuln_type": f.get("vuln_type", "unknown"), "severity": f.get("severity", "medium"), "endpoint": f.get("target_name", "unknown")})
                    break
            result = council_triage(finding)
            verdict = "SUBMIT" if result["submit"] else "NO-SUBMIT"
            return (
                f"\U0001f534 <b>Council Triage \u2014 Finding #{finding_id}</b>\n\n"
                f"Verdict: <b>{verdict}</b>\n"
                f"Recommended severity: <b>{result['recommended_severity']}</b>\n"
                f"Confidence: <b>{result['confidence']}</b>\n\n"
                f"<b>Reasoning:</b>\n{result['reasoning'][:600]}"
            )
        elif sub == "metrics":
            from red_bridge import compute_red_metrics
            m = compute_red_metrics()
            lines = ["\U0001f534 <b>Red Metrics — Time to Fix</b>\n"]
            lines.append(f"Total: {m['total']} | Fixed: {m['fixed']} | Pending: {m['pending']}")
            if m["avg_fix_hours"]:
                lines.append("\n<b>Avg fix time by severity:</b>")
                for sev in ("critical", "high", "medium", "low"):
                    if sev in m["avg_fix_hours"]:
                        lines.append(f"  {sev}: {m['avg_fix_hours'][sev]:.1f}h")
            if m["oldest_unfixed"]:
                o = m["oldest_unfixed"]
                lines.append(f"\n<b>Oldest unfixed:</b> {o.get('task_id', '?')} [{o.get('severity', '?')}] since {o.get('created_at', '?')}")
            else:
                lines.append("\nAll findings fixed!")
            return "\n".join(lines)
        return "Usage: /red [status|findings|sync|triage <id>|metrics]"
    except Exception as e:
        return f"Red error: {e}"
