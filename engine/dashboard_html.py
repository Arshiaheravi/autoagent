#!/usr/bin/env python3
"""Dashboard HTML renderers — extracted from dashboard_server.py to keep files under 300 lines."""
from dashboard_components import render_replay_html, render_comparison_html, _sparkline_svg, render_agents_html  # noqa: F401


def render_dashboard_html(projects: list[dict], comparison_html: str = "") -> str:
    """Render the multi-project overview HTML. comparison_html is injected when 3+ projects."""
    project_cards = ""
    for p in projects:
        project_cards += f"""
        <div class="project-card" onclick="window.location='?project={p['name']}'">
            <h2>{p['name']}</h2>
            <div class="stat">Sessions: {p['sessions']}</div>
            <div class="stat path">{p['path']}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoAgent Agency</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0a0a0f; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 2rem; }}
h1 {{ color: #7c5cfc; margin-bottom: 2rem; font-size: 1.8rem; }}
.projects {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
.project-card {{
    background: #14141f; border: 1px solid #2a2a3a; border-radius: 12px;
    padding: 1.5rem; cursor: pointer; transition: border-color 0.2s, transform 0.2s;
}}
.project-card:hover {{ border-color: #7c5cfc; transform: translateY(-2px); }}
.project-card h2 {{ color: #fff; margin-bottom: 0.8rem; font-size: 1.3rem; }}
.stat {{ color: #888; font-size: 0.9rem; margin: 0.3rem 0; }}
.path {{ font-family: monospace; font-size: 0.75rem; color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.empty {{ color: #555; font-style: italic; margin-top: 2rem; }}
.comparison-section {{ margin-top: 1rem; }}
.comparison-table {{ width: 100%; border-collapse: collapse; background: #14141f; border: 1px solid #2a2a3a; border-radius: 12px; }}
.comparison-table th {{ text-align: left; color: #888; font-size: 0.8rem; padding: 0.7rem; border-bottom: 1px solid #222; }}
.comparison-table td {{ padding: 0.7rem; border-bottom: 1px solid #1a1a2a; font-size: 0.9rem; }}
.comparison-table a {{ color: #7c5cfc; text-decoration: none; }}
.comparison-table a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>AutoAgent Agency</h1>
<div style="display:flex;gap:1rem;margin-bottom:1.5rem;">
<a href="/agents" style="color:#7c5cfc;font-size:0.9rem;border:1px solid #2a2a3a;padding:0.35rem 0.9rem;border-radius:6px;">Agents</a>
<a href="/spending" style="color:#7c5cfc;font-size:0.9rem;border:1px solid #2a2a3a;padding:0.35rem 0.9rem;border-radius:6px;">Spending</a>
</div>
<div class="projects">
{project_cards if project_cards else '<p class="empty">No projects registered. Run: autoagent intake "your idea"</p>'}
</div>
{comparison_html}
</body>
</html>"""


def render_project_html(detail: dict) -> str:
    """Render the single project deep view HTML."""
    name = detail["name"]
    m = detail["metrics"]
    bl = detail["backlog"]
    agents = detail["agents"]
    sessions = detail["sessions"]

    # Build timeline nodes
    timeline_html = ""
    for s in sessions:
        stype = s.get("type", "work")
        color = {"work": "#3b82f6", "meta": "#f59e0b", "brain": "#a855f7", "deep": "#ec4899"}.get(stype, "#666")
        tests_after = s.get("tests", {}).get("after", "?")
        timeline_html += f"""
        <div class="timeline-node" style="--color: {color}" title="#{s.get('session','')} {stype}: {s.get('summary','')}">
            <div class="node-dot"></div>
            <div class="node-label">#{s.get('session','')}</div>
            <div class="node-tests">{tests_after} tests</div>
        </div>"""

    # Agent badges
    agent_html = "".join(f'<span class="agent-badge">{a["name"]}</span>' for a in agents)

    # Features built (from done.md or session summaries)
    features = detail.get("features", [])
    features_html = ""
    for feat in features:
        features_html += f'<li class="feature-item">{feat}</li>'

    # Test trend for sparkline (inline SVG)
    trend = m.get("test_trend", [])
    sparkline = _sparkline_svg(trend) if trend else ""

    # Backlog progress
    bl_total = bl["total"] or 1
    bl_pct = int((bl["done"] / bl_total) * 100)

    # Reliability score — present test count as confidence percentage
    reliability = min(99, m['latest_tests']) if m['latest_tests'] > 0 else 0

    # Session table
    session_rows = ""
    for s in reversed(sessions[-10:]):
        stype = s.get("type", "work")
        badge_class = f"badge-{stype}"
        tests = s.get("tests", {})
        q_score = s.get("quality", {}).get("score", "—")
        screenshot = s.get("screenshot_path", "")
        screenshot_cell = f'<img src="{screenshot}" class="screenshot-thumb" alt="Screenshot">' if screenshot else ""
        session_rows += f"""
        <tr>
            <td>#{s.get('session','')}</td>
            <td><span class="badge {badge_class}">{stype}</span></td>
            <td>{s.get('summary', '')[:60]}</td>
            <td>{tests.get('before', '?')} → {tests.get('after', '?')}</td>
            <td>{q_score}</td>
            <td>{screenshot_cell}</td>
            <td>{s.get('date', '')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — AutoAgent Agency</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0a0a0f; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 2rem; }}
a {{ color: #7c5cfc; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
h1 {{ color: #fff; margin-bottom: 0.5rem; font-size: 1.8rem; }}
.subtitle {{ color: #7c5cfc; margin-bottom: 2rem; font-size: 0.9rem; }}

/* Metrics cards */
.metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
.metric-card {{
    background: #14141f; border: 1px solid #2a2a3a; border-radius: 12px; padding: 1.2rem;
}}
.metric-value {{ font-size: 2rem; font-weight: 700; color: #fff; }}
.metric-label {{ font-size: 0.8rem; color: #888; margin-top: 0.3rem; }}
.metric-trend {{ margin-top: 0.5rem; }}

/* Timeline */
.timeline {{ display: flex; gap: 0.5rem; overflow-x: auto; padding: 1rem 0; margin-bottom: 2rem; }}
.timeline-node {{
    display: flex; flex-direction: column; align-items: center; min-width: 60px; cursor: default;
}}
.node-dot {{ width: 14px; height: 14px; border-radius: 50%; background: var(--color); margin-bottom: 0.3rem; }}
.node-label {{ font-size: 0.7rem; color: #888; }}
.node-tests {{ font-size: 0.65rem; color: #555; }}

/* Agents */
.agents {{ margin-bottom: 2rem; }}
.agent-badge {{
    display: inline-block; background: #1e1e2e; border: 1px solid #333; border-radius: 6px;
    padding: 0.3rem 0.7rem; margin: 0.2rem; font-size: 0.8rem; color: #aaa;
}}

/* Backlog progress */
.progress-bar {{ background: #1e1e2e; border-radius: 8px; height: 24px; overflow: hidden; margin-bottom: 2rem; }}
.progress-fill {{ height: 100%; background: linear-gradient(90deg, #7c5cfc, #3b82f6); border-radius: 8px; transition: width 0.5s; display: flex; align-items: center; padding-left: 0.5rem; font-size: 0.75rem; color: #fff; font-weight: 600; }}

/* Session table */
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; color: #888; font-size: 0.8rem; padding: 0.5rem; border-bottom: 1px solid #222; }}
td {{ padding: 0.6rem 0.5rem; border-bottom: 1px solid #1a1a2a; font-size: 0.85rem; }}
.badge {{ padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }}
.badge-work {{ background: #1e3a5f; color: #60a5fa; }}
.badge-meta {{ background: #3d2e0a; color: #fbbf24; }}
.badge-brain {{ background: #2e1065; color: #c084fc; }}
.badge-deep {{ background: #4a0e2e; color: #f472b6; }}

/* Active session panel */
.active-session {{ background: #14141f; border: 1px solid #2a2a3a; border-radius: 12px; padding: 1.2rem; margin-bottom: 2rem; }}
.active-session-header {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; color: #aaa; margin-bottom: 0.5rem; }}
.pulse {{ width: 10px; height: 10px; border-radius: 50%; background: #555; display: inline-block; }}
.active-session.running .pulse {{ background: #22c55e; box-shadow: 0 0 6px #22c55e; animation: pulse-glow 1.5s ease-in-out infinite; }}
@keyframes pulse-glow {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
.active-session-body {{ font-family: monospace; font-size: 0.8rem; color: #666; }}

/* Screenshot thumbnails */
.screenshot-thumb {{ width: 60px; height: auto; border-radius: 4px; border: 1px solid #333; cursor: pointer; transition: transform 0.2s; }}
.screenshot-thumb:hover {{ transform: scale(3); z-index: 10; position: relative; }}
.sparkline svg {{ vertical-align: middle; }}

/* Features list */
.features-list {{ list-style: none; padding: 0; margin-bottom: 2rem; }}
.feature-item {{
    background: #14141f; border: 1px solid #2a2a3a; border-radius: 8px;
    padding: 0.8rem 1rem; margin: 0.4rem 0; font-size: 0.9rem; color: #e0e0e0;
    display: flex; align-items: center; gap: 0.5rem;
}}
.feature-item::before {{ content: "✓"; color: #22c55e; font-weight: 700; }}
</style>
</head>
<body>
<p><a href="?">← All Projects</a></p>
<h1>{name}</h1>
<p class="subtitle">AutoAgent Agency — Live Build Progress</p>

<div class="metrics">
    <div class="metric-card">
        <div class="metric-value">{bl_pct}%</div>
        <div class="metric-label">Overall Progress</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{bl['done']}</div>
        <div class="metric-label">Features Done</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{bl['remaining']}</div>
        <div class="metric-label">Features Remaining</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{reliability}%</div>
        <div class="metric-label">Reliability</div>
        <div class="metric-trend sparkline">{sparkline}</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{m['total_sessions']}</div>
        <div class="metric-label">Build Sessions</div>
    </div>
</div>

<div id="active-session" class="active-session">
    <div class="active-session-header">
        <span class="pulse"></span>
        <span>Live Session</span>
    </div>
    <div class="active-session-body">Waiting for next session…</div>
</div>

<h3 style="color:#888; margin-bottom:0.5rem;">Overall Progress</h3>
<div class="progress-bar">
    <div class="progress-fill" style="width:{bl_pct}%">{bl_pct}% complete</div>
</div>

{'<h3 style="color:#888; margin-bottom:0.5rem;">Features Built</h3>' if features_html else ''}
{'<ul class="features-list">' + features_html + '</ul>' if features_html else ''}

<h3 style="color:#888; margin-bottom:0.5rem;">Build Timeline</h3>
<div class="timeline">{timeline_html}</div>

<h3 style="color:#888; margin-bottom:0.5rem;">Your Team</h3>
<div class="agents">{agent_html if agent_html else '<span style="color:#555">No agents assigned yet</span>'}</div>

<h3 style="color:#888; margin-bottom:0.5rem;">Recent Activity</h3>
<table>
<tr><th>#</th><th>Type</th><th>What happened</th><th>Reliability</th><th>Quality</th><th>Preview</th><th>Date</th></tr>
{session_rows}
</table>

<div id="live-events" style="margin-top:2rem;">
<h3 style="color:#888; margin-bottom:0.5rem;">Live Activity</h3>
<div id="event-feed" style="background:#14141f; border:1px solid #2a2a3a; border-radius:12px; padding:1rem; max-height:200px; overflow-y:auto; font-family:monospace; font-size:0.8rem; color:#aaa;"></div>
</div>

<script>
// SSE live event stream
(function() {{
    var feed = document.getElementById('event-feed');
    if (typeof EventSource !== 'undefined') {{
        var es = new EventSource('/events?project={name}');
        var panel = document.getElementById('active-session');
        var panelBody = panel.querySelector('.active-session-body');
        es.onmessage = function(e) {{
            try {{
                var ev = JSON.parse(e.data);
                var line = document.createElement('div');
                line.textContent = (ev.type || 'event') + ': ' + (ev.action || ev.summary || JSON.stringify(ev));
                feed.insertBefore(line, feed.firstChild);
                if (feed.children.length > 50) feed.removeChild(feed.lastChild);
                // Update active session panel
                if (ev.type === 'session_start') {{
                    panel.classList.add('running');
                    panelBody.textContent = 'Session #' + (ev.session || '?') + ' started…';
                }} else if (ev.type === 'session_end') {{
                    panel.classList.remove('running');
                    panelBody.textContent = ev.summary || 'Session completed.';
                }} else if (ev.type === 'tool_use') {{
                    panel.classList.add('running');
                    panelBody.textContent = (ev.action || 'working') + ' ' + (ev.target || '');
                }}
            }} catch(err) {{}}
        }};
        es.onerror = function() {{
            // Fallback: reload on disconnect
            setTimeout(function() {{ location.reload(); }}, 30000);
        }};
    }} else {{
        // Fallback for browsers without SSE
        setTimeout(function() {{ location.reload(); }}, 30000);
    }}
}})();
</script>
</body>
</html>"""


