#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoAgent Agency — Complex CLI Command Handlers

Extracted from cli.py to keep it under 300 lines.
Contains: cmd_run, cmd_agent, cmd_skill, cmd_logs, cmd_validate.
"""
from registry import get, list_projects, validate_project
from runner import run_project, run_continuous, show_status, ask_mode
from session_helpers import filter_sessions
from orchestrator import generate_agent_md, list_agents
from cli_parse import parse_positive_int


def cmd_run(args):
    if not args:
        print("  Error: specify a project name. Run: autoagent list")
        return

    rest = list(args)

    continuous = "--continuous" in rest
    run_all = "--all" in rest
    until_time = None
    forced_type = None
    test_mode = "--test" in rest
    tasks_limit = None
    forced_mode = None
    if "--cli" in rest:
        forced_mode = "cli"
    elif "--api" in rest:
        forced_mode = "api"

    if "--until" in rest:
        idx = rest.index("--until")
        if idx + 1 < len(rest):
            until_time = rest[idx + 1]
    if "--once" in rest:
        tasks_limit = 1
    if "--tasks" in rest:
        tasks_limit, err = parse_positive_int(rest, "--tasks", tasks_limit)
        if err:
            print(f"  Error: {err}")
            return
    if "--type" in rest:
        idx = rest.index("--type")
        if idx + 1 < len(rest):
            forced_type = rest[idx + 1]
            if forced_type not in ("work", "meta", "brain", "deep", "audit", "knowledge"):
                print(f"  Error: unknown session type '{forced_type}'")
                return

    # Agency-wide lock: block a manual run from spending concurrently with a
    # cron/launchd run (or a second terminal) — same guard the autonomous path uses.
    # --test is read-only, so it skips the lock.
    if not test_mode:
        from self_improve import _acquire_agency_lock, _release_agency_lock
        import atexit
        if not _acquire_agency_lock():
            return
        atexit.register(_release_agency_lock)

    # Continuous + --all mode: round-robin across all registered projects
    if continuous and run_all:
        projects = list_projects()
        if not projects:
            print("  Error: no projects registered. Run: autoagent register <name> <path>")
            return
        contexts = []
        for p in projects:
            try:
                ctx = get(p["name"])
                ctx.ensure_symlink()
                contexts.append(ctx)
            except KeyError:
                pass
        if not contexts:
            print("  Error: no valid projects found.")
            return
        run_continuous(contexts, until=until_time, forced_type=forced_type)
        return

    # Need a project name for all other modes
    if run_all:
        print("  Error: --all requires --continuous (round-robin across projects).")
        print("  For one project: autoagent run <name>")
        return
    project_name = args[0]
    if project_name.startswith("--"):
        print(f"  Error: expected a project name, got flag '{project_name}'. Run: autoagent list")
        return

    try:
        ctx = get(project_name)
    except KeyError as e:
        print(f"  Error: {e}")
        return

    # Continuous mode for a single project
    if continuous:
        if not test_mode:
            if forced_mode:
                ctx.config["mode"] = forced_mode
            else:
                try:
                    ctx.config["mode"] = ask_mode()
                except (EOFError, KeyboardInterrupt):
                    ctx.config["mode"] = "cli"
        ctx.ensure_symlink()
        run_continuous([ctx], until=until_time, forced_type=forced_type)
        return

    # Mode: explicit --cli/--api wins; else prompt (auto-cli when non-interactive)
    if not test_mode:
        if forced_mode:
            ctx.config["mode"] = forced_mode
        else:
            try:
                ctx.config["mode"] = ask_mode()
            except (EOFError, KeyboardInterrupt):
                ctx.config["mode"] = "cli"
        print(f"\n  [AutoAgent] Mode: {ctx.config['mode'].upper()}")

    ctx.ensure_symlink()
    run_project(ctx, tasks_limit=tasks_limit, forced_type=forced_type, test_mode=test_mode)


def cmd_agent(args):
    if not args or args[0] == "list":
        project_name = args[1] if len(args) > 1 else None
        if not project_name:
            print("  Usage: autoagent agent list <project>")
            return
        try:
            ctx = get(project_name)
            agents = list_agents(ctx)
            if not agents:
                print(f"\n  No agents defined for {project_name}.")
                return
            print(f"\n  Agents for {project_name}:")
            print(f"  {'Name':<25} {'Description'}")
            print(f"  {'─' * 25} {'─' * 50}")
            for a in agents:
                print(f"  {a['name']:<25} {a['description'][:50]}")
            print()
        except KeyError as e:
            print(f"  Error: {e}")

    elif args[0] == "create":
        if len(args) < 4:
            print("  Usage: autoagent agent create <project> <agent-name> \"description\"")
            return
        project_name, agent_name, description = args[1], args[2], " ".join(args[3:])
        try:
            ctx = get(project_name)
            content = generate_agent_md(agent_name, description, project_name)
            agent_file = ctx.agents_dir / f"{agent_name}.md"
            agent_file.write_text(content, encoding="utf-8")
            print(f"  Created agent '{agent_name}' for {project_name}")
            print(f"    → {agent_file}")
            print(f"  Edit the file to refine the agent's expertise and protocols.")
        except KeyError as e:
            print(f"  Error: {e}")

    elif args[0] == "stats":
        from agency_db import get_top_agents
        agents = get_top_agents(limit=20)
        if not agents:
            print("\n  No agent performance data yet.")
            return
        print(f"\n  {'Agent':<30} {'Sessions':>8} {'Success':>8} {'Failed':>8} {'Rate':>7} {'Avg Q':>6} {'Conf':>6}")
        print(f"  {'─' * 30} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 7} {'─' * 6} {'─' * 6}")
        for a in agents:
            name = f"{a['project']}/{a['name']}"
            rate = f"{a['success_rate']*100:.0f}%"
            avg_q = f"{a.get('avg_quality', 0):.0f}" if a.get('avg_quality') else "—"
            sessions = a["total_sessions"]
            conf = "high" if sessions >= 20 else ("med" if sessions >= 5 else "low")
            print(f"  {name:<30} {sessions:>8} {a['successful']:>8} {a['failed']:>8} {rate:>7} {avg_q:>6} {conf:>6}")
        print()
    else:
        print("  Usage: autoagent agent <list|create|stats> ...")


def cmd_skill(args):
    from registry import promote_skill
    if not args:
        print("  Usage: autoagent skill promote <project> <skill>")
        return
    if args[0] == "promote":
        if len(args) < 3:
            print("  Usage: autoagent skill promote <project> <skill>")
            return
        project_name, skill_name = args[1], args[2]
        try:
            promote_skill(project_name, skill_name)
            print(f"  Promoted '{skill_name}' from {project_name} → shared skills")
        except (KeyError, FileNotFoundError) as e:
            print(f"  Error: {e}")
    else:
        print(f"  Unknown skill subcommand: {args[0]}")
        print("  Usage: autoagent skill promote <project> <skill>")


def cmd_validate(args):
    if not args:
        print("  Usage: autoagent validate <project>")
        return
    try:
        ctx = get(args[0])
    except KeyError as e:
        print(f"  Error: {e}")
        return
    warnings = validate_project(ctx)
    if not warnings:
        print(f"\n  {ctx.name}: All checks passed ✓")
    else:
        print(f"\n  {ctx.name}: {len(warnings)} warning(s)")
        for w in warnings:
            print(f"    ⚠ {w}")
    print()


def cmd_logs(args):
    if not args:
        print("  Usage: autoagent logs <project> [--type work|meta|brain] [--last N] [--search \"term\"]")
        return

    project_name = args[0]
    rest = args[1:]

    try:
        ctx = get(project_name)
    except KeyError as e:
        print(f"  Error: {e}")
        return

    session_type = None
    last_n = None
    search = None

    if "--type" in rest:
        idx = rest.index("--type")
        if idx + 1 < len(rest):
            session_type = rest[idx + 1]
    if "--last" in rest:
        last_n, err = parse_positive_int(rest, "--last")
        if err:
            print(f"  Error: {err}")
            return
    if "--search" in rest:
        idx = rest.index("--search")
        if idx + 1 < len(rest):
            search = rest[idx + 1]

    sessions = filter_sessions(
        ctx.sessions_file,
        session_type=session_type,
        last_n=last_n,
        search=search,
    )

    if not sessions:
        print(f"\n  No sessions found for {project_name} with those filters.")
        return

    print(f"\n  Session logs for {project_name} ({len(sessions)} results):\n")
    for s in sessions:
        sid = s.get("session", "?")
        stype = s.get("type", "?")
        date = s.get("date", "")
        summary = s.get("summary", "")
        print(f"  #{sid:<4} [{stype:<5}] {date}  {summary}")
    print()


def cmd_replicate(args):
    """autoagent replicate <url-or-image> [--project NAME] [--no-wait] [--resume SLUG]"""
    if not args:
        print("  Usage: autoagent replicate <url|image> [--project NAME] [--no-wait]")
        print("         autoagent replicate --resume <slug> [--project NAME]")
        return

    from replicator import replicate, resume

    project = None
    wait_for_review = True
    resume_slug = None
    positional = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        elif a == "--no-wait":
            wait_for_review = False
            i += 1
        elif a == "--resume" and i + 1 < len(args):
            resume_slug = args[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1

    if resume_slug:
        print(f"  Resuming replica '{resume_slug}'...")
        result = resume(resume_slug, project=project)
    else:
        if not positional:
            print("  Error: provide a URL or image path.")
            return
        src = positional[0]
        print(f"  Replicating: {src}")
        result = replicate(src, project=project, wait_for_review=wait_for_review)

    status = result.get("status", "?")
    if status == "failed":
        print(f"  ✗ Failed: {result.get('error', 'unknown')}")
        return
    slug = result.get("slug", "?")
    brief = result.get("brief_path", "?")
    print(f"\n  Status: {status}")
    print(f"  Slug:   {slug}")
    print(f"  Brief:  {brief}")
    if status == "pending_review":
        print(f"\n  Edit the brief, then run: autoagent replicate --resume {slug}")
    elif status == "ready":
        synth = result.get("council_synthesis", "")
        if synth:
            print(f"  Council: {synth[:200]}")
        if project:
            print(f"  Backlog: task added for '{project}'. Next WORK session will build it.")
    print()
