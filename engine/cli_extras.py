"""CLI subcommands — extracted from cli.py to stay under 300-line budget."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import get, list_projects
from cli_parse import parse_positive_int


def cmd_graph(args):
    """Show task graph analysis for a project."""
    if not args:
        print("  Usage: autoagent graph <project>")
        return
    try:
        ctx = get(args[0])
        from task_graph import TaskGraph
        backlog = ctx.memory_dir / "backlog.md"
        if not backlog.exists():
            print("  No backlog found.")
            return
        graph = TaskGraph.from_backlog(backlog.read_text(encoding="utf-8"))
        s = graph.summary()
        print(f"\n  Task Graph — {ctx.name}")
        print(f"  {'─' * 40}")
        print(f"  Total tasks:      {s['total']}")
        print(f"  Completed:        {s['done']}")
        print(f"  Remaining:        {s['remaining']}")
        print(f"  Ready now:        {s['ready_now']}")
        print(f"  Blocked:          {s['blocked']}")
        print(f"  Parallel batches: {s['parallel_batches']}")
        print(f"  Critical path:    {s['critical_path_length']} steps")
        print(f"  Min sequential:   {s['min_sequential_steps']} batches")

        ready = graph.find_ready()
        if ready:
            print(f"\n  Ready tasks:")
            for t in ready[:5]:
                agent = f" [{t.agent_hint}]" if t.agent_hint else ""
                pri = f" ({t.priority})" if t.priority != "medium" else ""
                print(f"    - {t.name}{agent}{pri}")

        blocked = graph.blocked_tasks()
        if blocked:
            print(f"\n  Blocked tasks:")
            for t, blockers in blocked[:5]:
                print(f"    - {t.name} (waiting on: {', '.join(blockers)})")

        batches = graph.find_parallel_batches()
        if batches:
            print(f"\n  Next parallel batch ({len(batches[0])} tasks):")
            for t in batches[0]:
                agent = f" [{t.agent_hint}]" if t.agent_hint else ""
                print(f"    - {t.name}{agent}")
        print()
    except KeyError as e:
        print(f"  Error: {e}")


def cmd_improve(args):
    """Run self-improvement layers: share, metrics, gate, skills."""
    from self_improve import share_knowledge_across_projects, inject_production_metrics, quality_gate_check, generate_skill_from_knowledge
    if not args or args[0] == "share":
        count = share_knowledge_across_projects()
        print(f"  Shared {count} rules across projects.")
    elif args[0] == "metrics":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        print(f"  {inject_production_metrics(ctx) or 'No metrics.'}")
    elif args[0] == "gate":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        import json
        print(json.dumps(quality_gate_check(ctx), indent=2))
    elif args[0] == "skills":
        name = args[1] if len(args) > 1 else list_projects()[0]["name"]
        ctx = get(name)
        skill = generate_skill_from_knowledge(ctx)
        print(f"  Generated: {skill}" if skill else "  No patterns found.")
    else:
        print("  Usage: autoagent improve [share|metrics|gate|skills] [project]")


def cmd_usage(args):
    """Show per-project token usage."""
    from usage import show_usage, show_usage_all
    period = "today"
    project_name = None
    for a in args:
        if a in ("today", "week", "all"):
            period = a
        else:
            project_name = a
    if project_name:
        try:
            ctx = get(project_name)
            show_usage(ctx, period)
        except KeyError as e:
            print(f"  Error: {e}")
    else:
        show_usage_all(period)


def cmd_fallback(args):
    """Show fallback model status and task routing."""
    from model_fallback import get_fallback_status, TASK_ROUTING
    status = get_fallback_status()
    print("\n  Model Fallback — Task-Aware Routing")
    print("  ────────────────────────────────────")
    print("  Primary: Claude Opus (Max plan)")
    print()
    for label, info in status.items():
        icon = "●" if info["state"] == "ready" else "○"
        print(f"  {icon} {label:<18} — {info['strengths']}")
    print()
    print("  Task routing (when Claude is unavailable):")
    for task, chain in TASK_ROUTING.items():
        labels = [f"{m.split('-')[0].upper()}" for m in chain]
        print(f"    {task:<12} → {' → '.join(labels)}")
    print()
    print("  Set keys: GEMINI_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY")
    print()


def cmd_parallel(args):
    """Run parallel sessions using worktree isolation."""
    if not args:
        print("  Usage: autoagent parallel <project> [--max N]")
        return
    project_name = args[0]
    max_parallel = 2
    if "--max" in args:
        max_parallel, err = parse_positive_int(args, "--max", max_parallel)
        if err:
            print(f"  Error: {err}")
            return
    try:
        ctx = get(project_name)
        from launcher import launch_parallel
        from runner import _next_session_num
        session_num = _next_session_num(ctx)
        results = launch_parallel(ctx, session_num, max_parallel=max_parallel)
        for r in results:
            icon = "OK" if r["success"] else "FAIL"
            print(f"  [{icon}] {r['task']} (agent: {r['agent']})")
    except KeyError as e:
        print(f"  Error: {e}")


def cmd_auto(args):
    """Run 1 session per project autonomously (cron-safe)."""
    from self_improve import run_autonomous
    project_names = args if args else None
    result = run_autonomous(project_names)
    import json
    print(json.dumps(result, indent=2))


def cmd_director(args):
    """Launch the terminal director shell."""
    from director_shell import main
    main()


def cmd_flags(args):
    """List or toggle feature flags."""
    if not args:
        print("  Usage: autoagent flags <project> [flag on|off]")
        return
    try:
        ctx = get(args[0])
        from features import list_flags, set_flag, AVAILABLE_FLAGS
        if len(args) == 1:
            for name, on in list_flags(ctx).items():
                print(f"  {'ON' if on else 'OFF':>3}  {name}")
        elif len(args) >= 3:
            flag, state = args[1], args[2].lower() in ("on", "true", "1", "yes")
            set_flag(ctx, flag, state)
            print(f"  {flag} → {'ON' if state else 'OFF'}")
    except KeyError as e:
        print(f"  Error: {e}")


def cmd_cleanup(args):
    """Run the Engineering cleanup crew scan."""
    from cleanup import run_cleanup_cli
    run_cleanup_cli(args)


def cmd_org(args):
    """Show department, agent, skill, and loop organization."""
    from org_model import build_org_report, format_org_report
    report = build_org_report()
    if "--json" in args:
        import json
        print(json.dumps(report, indent=2))
        if "--strict" in args and not report.get("strict_ok", False):
            raise SystemExit(1)
        return
    print(format_org_report(report))
    if "--strict" in args and not report.get("strict_ok", False):
        raise SystemExit(1)


def cmd_db(args):
    """Database maintenance commands."""
    if not args or args[0] not in ("sync", "audit", "prune-test-data", "prune-orphans", "dedupe-sessions"):
        print("  Usage: autoagent db <sync|audit|dedupe-sessions|prune-test-data|prune-orphans> [project|--all] [--apply]")
        return
    if args[0] == "audit":
        from db_maintenance import audit_database, format_audit
        print(format_audit(audit_database()))
        return
    if args[0] in ("prune-test-data", "prune-orphans"):
        apply = "--apply" in args
        from db_maintenance import (
            prune_test_data, prune_orphans, format_prune_result,
        )
        if args[0] == "prune-test-data":
            result = prune_test_data(apply=apply)
            print(format_prune_result(result, "Prune Test Data"))
        else:
            result = prune_orphans(apply=apply)
            print(format_prune_result(result, "Prune Orphans"))
        if not apply:
            print("  Re-run with --apply to delete these DB rows.")
        return
    if args[0] == "dedupe-sessions":
        apply = "--apply" in args
        target = next((a for a in args[1:] if not a.startswith("--")), None)
        if target == "--all":
            target = None
        from db_maintenance import dedupe_sessions, format_dedupe_result
        result = dedupe_sessions(project=target, apply=apply)
        print(format_dedupe_result(result))
        if not apply:
            print("  Re-run with --apply to collapse duplicate session rows.")
        return
    target = args[1] if len(args) > 1 and args[1] != "--all" else None
    from session_db_sync import sync_sessions_file_to_agency_db
    projects = []
    if target:
        projects = [get(target)]
    else:
        for p in list_projects():
            try:
                projects.append(get(p["name"]))
            except KeyError:
                pass
    total = 0
    for ctx in projects:
        try:
            count = sync_sessions_file_to_agency_db(ctx, raise_errors=True)
        except Exception as exc:
            print(f"  Error syncing {ctx.name}: {exc}")
            raise SystemExit(1)
        total += count
        print(f"  {ctx.name}: synced {count} session(s)")
    print(f"  Total synced: {total}")
