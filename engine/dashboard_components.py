#!/usr/bin/env python3
"""Dashboard component renderers — comparison table, replay timeline, sparkline SVG, health endpoint."""
import json
import time
from datetime import date
from pathlib import Path


def render_replay_html(project_name: str, session_id: int, events: list[dict]) -> str:
    """Render session replay HTML — a timeline of tool calls with timestamps and error highlighting."""
    timeline_items = ""
    for ev in events:
        ts = ev.get("timestamp", "")
        # Extract HH:MM:SS from ISO timestamp
        time_str = ts[11:19] if len(ts) >= 19 else ts
        ev_type = ev.get("type", "unknown")
        action = ev.get("action", "")
        target = ev.get("target", "")
        error = ev.get("error", "")
        summary = ev.get("summary", "")

        # Determine CSS class
        error_class = " replay-error" if error else ""

        # Build description
        if ev_type == "session_start":
            desc = "Session Start"
        elif ev_type == "session_end":
            desc = f"Session End{' — ' + summary if summary else ''}"
        elif ev_type == "tool_use":
            desc = f"{action} {target}".strip()
        else:
            desc = ev_type

        error_html = f'<div class="replay-error-msg">{error}</div>' if error else ""

        timeline_items += f"""
        <div class="replay-event{error_class}">
            <div class="replay-time">{time_str}</div>
            <div class="replay-dot"></div>
            <div class="replay-content">
                <div class="replay-type">{ev_type}</div>
                <div class="replay-desc">{desc}</div>
                {error_html}
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Session #{session_id} Replay — {project_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0a0a0f; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 2rem; }}
a {{ color: #7c5cfc; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
h1 {{ color: #fff; margin-bottom: 0.5rem; font-size: 1.8rem; }}
.subtitle {{ color: #7c5cfc; margin-bottom: 2rem; font-size: 0.9rem; }}
.replay-timeline {{ position: relative; padding-left: 2rem; }}
.replay-timeline::before {{
    content: ''; position: absolute; left: 0.9rem; top: 0; bottom: 0;
    width: 2px; background: #2a2a3a;
}}
.replay-event {{
    display: flex; align-items: flex-start; gap: 1rem; padding: 0.8rem 0;
    position: relative;
}}
.replay-event.replay-error .replay-dot {{ background: #ef4444; box-shadow: 0 0 8px #ef4444; }}
.replay-event.replay-error .replay-content {{ border-color: #ef4444; }}
.replay-time {{ font-family: monospace; font-size: 0.8rem; color: #888; min-width: 70px; }}
.replay-dot {{
    width: 12px; height: 12px; border-radius: 50%; background: #7c5cfc;
    flex-shrink: 0; margin-top: 0.2rem;
}}
.replay-content {{
    background: #14141f; border: 1px solid #2a2a3a; border-radius: 8px;
    padding: 0.8rem 1rem; flex: 1;
}}
.replay-type {{ font-size: 0.7rem; color: #888; text-transform: uppercase; margin-bottom: 0.3rem; }}
.replay-desc {{ font-size: 0.9rem; color: #e0e0e0; }}
.replay-error-msg {{ font-family: monospace; font-size: 0.8rem; color: #ef4444; margin-top: 0.4rem; padding: 0.4rem; background: #1a0a0a; border-radius: 4px; }}
.event-count {{ color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }}
</style>
</head>
<body>
<p><a href="?project={project_name}">← Back to {project_name}</a></p>
<h1>Session #{session_id} Replay</h1>
<p class="subtitle">{project_name} — Tool-by-Tool Activity</p>
<p class="event-count">{len(events)} events</p>
<div class="replay-timeline">
{timeline_items}
</div>
</body>
</html>"""


def render_comparison_html(projects: list[dict]) -> str:
    """Render a comparison table for 3+ projects — rows per project, columns for key metrics."""
    rows = ""
    for p in projects:
        name = p.get("name", "?")
        m = p.get("metrics", {})
        bl = p.get("backlog", {})
        sessions = m.get("total_sessions", 0)
        tests = m.get("latest_tests", 0)
        quality = m.get("avg_quality")
        quality_str = str(quality) if quality is not None else "—"
        trend = m.get("test_trend", [])
        sparkline = _sparkline_svg(trend) if len(trend) >= 2 else ""
        bl_total = bl.get("total", 0) or 1
        bl_done = bl.get("done", 0)
        progress = int((bl_done / bl_total) * 100)
        rows += f"""
        <tr>
            <td><a href="?project={name}">{name}</a></td>
            <td>{sessions}</td>
            <td>{tests} {sparkline}</td>
            <td>{quality_str}</td>
            <td>{progress}%</td>
        </tr>"""

    return f"""<div class="comparison-section">
<h3 style="color:#888; margin-bottom:0.8rem;">Project Comparison</h3>
<table class="comparison-table">
<tr><th>Project</th><th>Sessions</th><th>Tests</th><th>Quality</th><th>Progress</th></tr>
{rows}
</table>
</div>"""


def _sparkline_svg(values: list, width: int = 120, height: int = 30) -> str:
    """Generate an inline SVG sparkline from a list of numbers."""
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    step = width / (len(values) - 1)
    points = []
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(height - ((v - mn) / rng) * (height - 4) - 2, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{polyline}" fill="none" stroke="#7c5cfc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def render_agents_html(agents: list[dict]) -> str:
    """Render /agents page — bar chart of success rates, session counts, quality scores."""
    if not agents:
        return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Agent Performance</title>
<style>body{background:#0a0a0f;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:2rem;}
h1{color:#7c5cfc;margin-bottom:1rem;}</style></head>
<body><p><a href="/" style="color:#7c5cfc;">← Back</a></p><h1>Agent Performance</h1>
<p style="color:#555;font-style:italic;">No agent data yet. Run some sessions first.</p></body></html>"""

    max_sessions = max(a.get("total_sessions", 1) for a in agents) or 1
    rows = ""
    for a in agents:
        name = a.get("name", "?")
        project = a.get("project", "")
        total = a.get("total_sessions", 0)
        ok = a.get("successful", 0)
        fail = a.get("failed", 0)
        rate = a.get("success_rate", 0)
        quality = a.get("avg_quality")
        q_str = f"{quality:.0f}" if quality is not None else "—"
        pct = int(rate * 100)
        bar_w = int((total / max_sessions) * 100)
        bar_color = "#22c55e" if pct >= 80 else "#f59e0b" if pct >= 50 else "#ef4444"

        rows += f"""<tr>
<td><strong>{name}</strong><br><span style="color:#555;font-size:0.75rem;">{project}</span></td>
<td>{total}</td><td>{ok}</td><td>{fail}</td>
<td><span style="color:{bar_color};font-weight:600;">{pct}%</span></td>
<td>{q_str}</td>
<td><div style="background:#2a2a3a;border-radius:4px;height:18px;width:120px;">
<div style="background:{bar_color};border-radius:4px;height:18px;width:{bar_w}%;"></div></div></td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Performance — AutoAgent</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0a0f;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:2rem;}}
a{{color:#7c5cfc;text-decoration:none;}} a:hover{{text-decoration:underline;}}
h1{{color:#7c5cfc;margin-bottom:0.5rem;font-size:1.8rem;}}
.subtitle{{color:#888;margin-bottom:2rem;font-size:0.9rem;}}
table{{width:100%;border-collapse:collapse;background:#14141f;border:1px solid #2a2a3a;border-radius:12px;}}
th{{text-align:left;color:#888;font-size:0.8rem;padding:0.7rem;border-bottom:1px solid #222;}}
td{{padding:0.7rem;border-bottom:1px solid #1a1a2a;font-size:0.9rem;}}
</style></head>
<body>
<p><a href="/">← Back to Dashboard</a></p>
<h1>Agent Performance</h1>
<p class="subtitle">{len(agents)} agents across all projects</p>
<table>
<tr><th>Agent</th><th>Sessions</th><th>OK</th><th>Fail</th><th>Success</th><th>Quality</th><th>Activity</th></tr>
{rows}
</table>
</body></html>"""


# Module-level start time for uptime calculation
_START_TIME = time.monotonic()


def get_health_data() -> dict:
    """Return system health vitals as a dict — pure function over registry state.

    Keys: uptime_seconds, sessions_today, tests_passing, daily_cost, active_projects.
    """
    from registry import list_projects, get

    projects = list_projects()
    today_str = date.today().isoformat()
    sessions_today = 0
    tests_passing = 0
    daily_cost = 0.0

    for p in projects:
        try:
            ctx = get(p["name"])
        except KeyError:
            continue

        # Count today's sessions
        if ctx.sessions_file.exists():
            try:
                sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
                for s in sessions:
                    if s.get("date") == today_str:
                        sessions_today += 1
                # Latest test count from most recent session with test data
                for s in reversed(sessions):
                    after = s.get("tests", {}).get("after")
                    if after is not None:
                        tests_passing += after
                        break
            except Exception:
                pass

        # Daily cost from budget file
        if ctx.budget_file.exists():
            try:
                budget = json.loads(ctx.budget_file.read_text(encoding="utf-8"))
                daily_cost += budget.get(today_str, 0.0)
            except Exception:
                pass

    return {
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "sessions_today": sessions_today,
        "tests_passing": tests_passing,
        "daily_cost": round(daily_cost, 2),
        "active_projects": len(projects),
    }


def render_spending_html(period: str = "month") -> str:
    """Render /spending page — visual progress bars per model + provider totals."""
    try:
        from council_usage import get_provider_spending, get_budgets, get_spending
        from usage import get_weekly_usage, show_usage_all
        from registry import list_projects, get
    except ImportError as e:
        return f"<p>Import error: {e}</p>"

    provider_data = get_provider_spending(period)
    budgets = get_budgets()
    model_data = get_spending(period)

    # Claude Max (CLI) weekly tokens — aggregate across all projects, split by type
    max_input = max_output = max_cache = 0
    try:
        projects = list_projects()
        for p in projects:
            try:
                ctx = get(p["name"])
                from usage import get_weekly_usage
                u = get_weekly_usage(ctx)
                max_input += u.get("input_tokens", 0)
                max_output += u.get("output_tokens", 0)
                max_cache += u.get("cache_read_tokens", 0) + u.get("cache_creation_tokens", 0)
            except Exception:
                pass
    except Exception:
        pass
    max_billable = max_input + max_output  # cache tokens aren't billed the same way

    label = {"today": "Today", "week": "Last 7 days", "month": "Last 30 days"}.get(period, period)

    # Build provider rows
    provider_order = ["anthropic", "openai", "gemini", "deepseek"]
    provider_display = {
        "anthropic": ("Anthropic API", "#7c5cfc"),
        "openai":    ("OpenAI (GPT-4o)", "#10b981"),
        "gemini":    ("Google Gemini", "#3b82f6"),
        "deepseek":  ("DeepSeek", "#f59e0b"),
    }

    provider_rows = ""
    total_spend = 0.0
    for provider in provider_order:
        display_name, color = provider_display.get(provider, (provider, "#888"))
        pdata = provider_data.get(provider, {"cost_usd": 0.0, "calls": 0, "models": []})
        cost = pdata["cost_usd"]
        calls = pdata["calls"]
        budget = budgets.get(provider, 50.0)
        pct = min(int((cost / budget) * 100), 100) if budget > 0 else 0
        total_spend += cost

        bar_color = color
        if pct >= 90:
            bar_color = "#ef4444"
        elif pct >= 70:
            bar_color = "#f59e0b"

        model_list = ""
        for m in pdata.get("models", []):
            model_list += (
                f'<span class="model-tag">{m["model"]}: '
                f'{m["calls"]} calls · ${m["cost_usd"]:.4f}</span>'
            )

        provider_rows += f"""
        <div class="spend-row">
            <div class="spend-header">
                <span class="spend-name">{display_name}</span>
                <span class="spend-cost" style="color:{bar_color};">${cost:.4f}</span>
                <span class="spend-budget">/ ${budget:.0f} budget</span>
                <span class="spend-calls">{calls} calls</span>
            </div>
            <div class="spend-bar-bg">
                <div class="spend-bar-fill" style="width:{pct}%; background:{bar_color};"></div>
            </div>
            <div class="spend-models">{model_list}</div>
        </div>"""

    # Claude Max — info panel, no bar (quota isn't queryable; check claude.ai/settings)
    def _fmt(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)

    max_bar = f"""
        <div class="spend-row">
            <div class="spend-header">
                <span class="spend-name">Claude Max (CLI sessions — last 7 days)</span>
                <span class="spend-calls" style="margin-left:0;">
                    <a href="https://claude.ai/settings/usage" style="color:#7c5cfc;font-size:0.8rem;">
                        View quota →
                    </a>
                </span>
            </div>
            <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.4rem;">
                <div class="max-stat"><div class="max-label">Input</div><div class="max-val">{_fmt(max_input)}</div></div>
                <div class="max-stat"><div class="max-label">Output</div><div class="max-val">{_fmt(max_output)}</div></div>
                <div class="max-stat"><div class="max-label">Cache</div><div class="max-val">{_fmt(max_cache)}</div></div>
                <div class="max-stat"><div class="max-label">Billable (in+out)</div><div class="max-val" style="color:#7c5cfc;">{_fmt(max_billable)}</div></div>
            </div>
            <p style="font-size:0.75rem;color:#555;margin-top:0.8rem;">
                Quota % shown in Claude.ai → Settings → Usage. Cache tokens inflate totals but are not billed at full rate.
            </p>
        </div>"""

    period_links = ""
    for p, lbl in [("today", "Today"), ("week", "7 Days"), ("month", "30 Days")]:
        active = ' style="color:#fff; border-color:#7c5cfc;"' if p == period else ""
        period_links += f'<a href="/spending?period={p}" class="period-btn"{active}>{lbl}</a>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>API Spending — AutoAgent</title>
<meta http-equiv="refresh" content="30">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0a0f;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:2rem;}}
a{{color:#7c5cfc;text-decoration:none;}} a:hover{{text-decoration:underline;}}
h1{{color:#7c5cfc;margin-bottom:0.5rem;font-size:1.8rem;}}
.subtitle{{color:#888;margin-bottom:1.5rem;font-size:0.9rem;}}
.period-bar{{display:flex;gap:0.5rem;margin-bottom:2rem;}}
.period-btn{{
    padding:0.4rem 1rem;border:1px solid #2a2a3a;border-radius:6px;
    color:#888;font-size:0.85rem;cursor:pointer;
}}
.period-btn:hover{{border-color:#7c5cfc;color:#fff;}}
.section-title{{color:#888;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:1rem;}}
.spend-row{{
    background:#14141f;border:1px solid #2a2a3a;border-radius:10px;
    padding:1.2rem 1.5rem;margin-bottom:1rem;
}}
.spend-header{{display:flex;align-items:center;gap:1rem;margin-bottom:0.8rem;flex-wrap:wrap;}}
.spend-name{{font-weight:600;font-size:1rem;color:#fff;flex:1;}}
.spend-cost{{font-size:1.1rem;font-weight:700;}}
.spend-budget{{color:#555;font-size:0.85rem;}}
.spend-calls{{color:#555;font-size:0.8rem;margin-left:auto;}}
.spend-bar-bg{{background:#1e1e2e;border-radius:4px;height:10px;margin-bottom:0.6rem;overflow:hidden;}}
.spend-bar-fill{{height:10px;border-radius:4px;transition:width 0.3s;min-width:2px;}}
.spend-models{{display:flex;flex-wrap:wrap;gap:0.4rem;}}
.model-tag{{
    font-size:0.72rem;color:#888;background:#1e1e2e;
    padding:0.2rem 0.5rem;border-radius:4px;
}}
.max-stat{{background:#1e1e2e;border-radius:8px;padding:0.6rem 1rem;min-width:100px;}}
.max-label{{font-size:0.72rem;color:#555;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.25rem;}}
.max-val{{font-size:1.1rem;font-weight:600;color:#e0e0e0;}}
.total-row{{
    border:1px solid #3a2a6a;background:#1a1428;border-radius:10px;
    padding:1rem 1.5rem;display:flex;align-items:center;gap:1rem;margin-bottom:2rem;
}}
.total-label{{color:#888;font-size:0.9rem;}}
.total-amount{{color:#7c5cfc;font-size:1.4rem;font-weight:700;margin-left:auto;}}
</style></head>
<body>
<p style="margin-bottom:1.5rem;"><a href="/">← Back to Dashboard</a></p>
<h1>API Spending</h1>
<p class="subtitle">{label} · Council + external API usage</p>
<div class="period-bar">{period_links}</div>

<div class="total-row">
    <span class="total-label">Total API spend ({label.lower()})</span>
    <span class="total-amount">${total_spend:.4f}</span>
</div>

<p class="section-title">API Keys (Council)</p>
{provider_rows}

<p class="section-title" style="margin-top:2rem;">Claude Max Plan (CLI)</p>
{max_bar}
</body></html>"""
