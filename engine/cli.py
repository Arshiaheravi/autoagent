#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoAgent Agency — CLI Entry Point

Usage:
    autoagent list                              # list all projects
    autoagent run myapp --once                  # single session
    autoagent run myapp --tasks 6               # N sessions
    autoagent run myapp --once --type meta      # force session type
    autoagent run myapp --test                  # dry run
    autoagent status myapp                       # show spend + recent activity
    autoagent register myapp /path/to/repo      # register existing project
    autoagent migrate /path/to/v1/autoagent     # import V1 project
"""
import sys
import os

# Add engine directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import register, get, list_projects, remove, migrate_v1, promote_skill, extract_universal_rules, validate_project, AGENCY_HOME
from runner import run_project, run_continuous, show_status, ask_mode
from session_helpers import filter_sessions
from intake import setup_project, run_intake
from orchestrator import generate_agent_md, list_agents
from dashboard_server import serve as serve_dashboard
from init_agency import init as init_agency
from cli_commands import cmd_run, cmd_agent, cmd_skill, cmd_logs, cmd_validate, cmd_replicate
from cli_extras import (
    cmd_graph, cmd_improve, cmd_usage, cmd_fallback, cmd_parallel,
    cmd_auto, cmd_flags, cmd_director, cmd_cleanup, cmd_org, cmd_db,
)


def print_usage():
    print("""
  AutoAgent Agency — Autonomous AI Development Teams

  Usage:
    autoagent init                                 First-time setup (~/.autoagent)
    autoagent intake "idea description"            Start a new project from an idea
    autoagent intake --path /repo "description"   Intake with existing repo
    autoagent list                                List all projects
    autoagent run <project> [options]             Run sessions for a project
    autoagent status <project>                    Show spend + recent activity
    autoagent register <name> <path>              Register a project
    autoagent migrate <v1-autoagent-dir> [name]   Import V1 project
    autoagent agent list <project>                 List agents for a project
    autoagent agent create <project> <name> "desc" Create a new agent from description
    autoagent skill promote <project> <skill>     Promote a project skill to shared
    autoagent dashboard                           Open live dashboard (localhost:8080)
    autoagent director                            Open the terminal agency shell
    autoagent org [--json|--strict]             Show departments, agents, skills, loops
    autoagent db sync [project|--all]           Sync sessions.json into agency.db
    autoagent db audit                          Audit DB hygiene and routing confidence
    autoagent db dedupe-sessions [--apply]      Collapse duplicate DB session rows
    autoagent logs <project> [options]             Show filtered session history
    autoagent validate <project>                  Check project health
    autoagent cleanup [project|--path PATH]       Run Engineering cleanup crew scan
    autoagent graph <project>                     Show task dependency graph analysis
    autoagent parallel <project> [--max N]        Run parallel sessions via worktrees
    autoagent usage [project] [today|week|all]     Token usage per project
    autoagent replicate <url|image> [--project N] Capture ref + spec + handoff (Claude Design port)
    autoagent remove <project>                    Unregister a project

  Run options:
    --once              Single session
    --tasks N           Run N sessions
    --type work|meta|brain|deep|audit|knowledge  Force session type
    --test              Dry run (build prompt, don't execute)
    --continuous        Run sessions indefinitely (Ctrl-C to stop)
    --until HH:MM       Stop at a specific time (e.g. --until 09:00)
    --all               Cycle through ALL registered projects (round-robin)
""")


def cmd_list():
    projects = list_projects()
    if not projects:
        print("\n  No projects registered. Run: autoagent register <name> <path>")
        return
    print(f"\n  {'Name':<20} {'Sessions':<10} {'Path'}")
    print(f"  {'─' * 20} {'─' * 10} {'─' * 40}")
    for p in projects:
        print(f"  {p['name']:<20} {p['sessions']:<10} {p['path']}")
    print()


def cmd_status(args):
    if not args:
        for p in list_projects():
            try:
                ctx = get(p["name"])
                show_status(ctx)
            except Exception:
                pass
        return
    try:
        ctx = get(args[0])
        show_status(ctx)
    except KeyError as e:
        print(f"  Error: {e}")


def cmd_register(args):
    if len(args) < 2:
        print("  Usage: autoagent register <name> <path>")
        return
    name, path = args[0], args[1]
    try:
        ctx = register(name, path)
        print(f"  Registered '{name}' → {ctx.project_home}")
    except Exception as e:
        print(f"  Error: {e}")


def cmd_migrate(args):
    if not args:
        print("  Usage: autoagent migrate <v1-autoagent-dir> [name]")
        return
    v1_dir = args[0]
    name = args[1] if len(args) > 1 else None
    try:
        ctx = migrate_v1(v1_dir, name)
        print(f"  Migration complete: {ctx.name}")
    except Exception as e:
        print(f"  Error: {e}")


def cmd_intake(args):
    description = " ".join(args) if args else ""
    project_path = None
    if "--path" in args:
        idx = args.index("--path")
        if idx + 1 < len(args):
            project_path = args[idx + 1]
            description = " ".join(a for i, a in enumerate(args) if i != idx and i != idx + 1)
    run_intake(description=description, project_path=project_path)


def cmd_remove(args):
    if not args:
        print("  Usage: autoagent remove <project>")
        return
    remove(args[0])
    print(f"  Removed '{args[0]}' from registry (files preserved)")


from cli_red import cmd_red  # noqa: F401, E402


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_usage(); return
    cmd = args[0]
    rest = args[1:]
    commands = {
        "list": lambda: cmd_list(),
        "run": lambda: cmd_run(rest),
        "status": lambda: cmd_status(rest),
        "register": lambda: cmd_register(rest),
        "migrate": lambda: cmd_migrate(rest),
        "remove": lambda: cmd_remove(rest),
        "intake": lambda: cmd_intake(rest),
        "agent": lambda: cmd_agent(rest),
        "skill": lambda: cmd_skill(rest),
        "logs": lambda: cmd_logs(rest),
        "validate": lambda: cmd_validate(rest),
        "cleanup": lambda: cmd_cleanup(rest),
        "org": lambda: cmd_org(rest),
        "departments": lambda: cmd_org(rest),
        "db": lambda: cmd_db(rest),
        "dashboard": lambda: serve_dashboard(),
        "director": lambda: cmd_director(rest),
        "init": lambda: init_agency(AGENCY_HOME),
        "auto": lambda: cmd_auto(rest),
        "improve": lambda: cmd_improve(rest),
        "parallel": lambda: cmd_parallel(rest),
        "graph": lambda: cmd_graph(rest),
        "red": lambda: cmd_red(rest),
        "flags": lambda: cmd_flags(rest),
        "usage": lambda: cmd_usage(rest),
        "fallback": lambda: cmd_fallback(rest),
        "replicate": lambda: cmd_replicate(rest),
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"  Unknown command: {cmd}")
        print_usage()

if __name__ == "__main__":
    main()
