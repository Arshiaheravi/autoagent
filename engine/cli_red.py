"""CLI red subcommands — bridge with autonomous-hunter."""


def cmd_red(args):
    """Red team commands — bridge with autonomous-hunter."""
    if not args:
        print("  Usage: autoagent red [status|findings|sync <project>]")
        return
    sub = args[0]
    try:
        from red_bridge import get_bridge_stats, get_unverified_findings, sync_findings
        from registry import get, list_projects
        if sub == "status":
            s = get_bridge_stats()
            print(f"\n  Red Team Bridge")
            print(f"  {'─' * 30}")
            print(f"  Total findings:  {s['total_findings']}")
            print(f"  Fixed:           {s['verified']}")
            print(f"  Pending:         {s['pending']}")
            for sev, count in s["by_severity"].items():
                print(f"    {sev}: {count}")
        elif sub == "findings":
            for f in get_unverified_findings():
                print(f"  [{f['severity'].upper():>8}] {f['task_id']} — {f['vuln_type']}")
        elif sub == "sync":
            project = args[1] if len(args) > 1 else None
            projects = [get(project)] if project else [get(p["name"]) for p in list_projects()]
            total = sum(len(sync_findings(ctx)) for ctx in projects)
            print(f"  Synced {total} new findings → Build backlogs.")
        else:
            print("  Usage: autoagent red [status|findings|sync <project>]")
    except Exception as e:
        print(f"  Error: {e}")
