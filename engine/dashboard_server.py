#!/usr/bin/env python3
"""Dashboard server — serves project data and live dashboard HTML."""
import json
import re
import time
from html import escape as html_escape
from pathlib import Path
from typing import Optional

from registry import list_projects, get, AGENCY_HOME
from orchestrator import list_agents
from dashboard_html import render_dashboard_html, render_project_html, render_replay_html, render_comparison_html, _sparkline_svg
from dashboard_components import render_agents_html, get_health_data, render_spending_html
from event_emitter import read_events

def resolve_sse_events_file(project_name: Optional[str]) -> Optional[Path]:
    """Resolve the events file for a project. Returns None if project is missing or unknown."""
    if not project_name:
        return None
    try:
        ctx = get(project_name)
        return ctx.events_file
    except KeyError:
        return None


def get_session_events(events_file: Path, session_id: int) -> list[dict]:
    """Return events from a JSONL file filtered to a specific session ID."""
    all_events = read_events(events_file, last_n=10000)
    return [ev for ev in all_events if ev.get("session") == session_id]


# Deprecated — kept for backwards compat with existing tests that set it directly.
# New code should use resolve_sse_events_file() instead.
SSE_EVENTS_FILE: Optional[Path] = None


def get_projects_data() -> list[dict]:
    """Get summary data for all registered projects."""
    return list_projects()


def get_project_detail(name: str) -> Optional[dict]:
    """Get full detail for a single project — sessions, metrics, backlog, agents."""
    try:
        ctx = get(name)
    except KeyError:
        return None

    # Sessions
    sessions = []
    if ctx.sessions_file.exists():
        try:
            sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Metrics
    work_sessions = [s for s in sessions if s.get("type") == "work"]
    test_trend = []
    for s in sessions:
        tests = s.get("tests", {})
        after = tests.get("after")
        if after is not None:
            test_trend.append(after)

    latest_tests = test_trend[-1] if test_trend else 0

    # Quality score average from last 5 scored sessions
    scored = [s for s in sessions if s.get("quality", {}).get("score") is not None]
    avg_quality = None
    if scored:
        last5 = scored[-5:]
        avg_quality = round(sum(s["quality"]["score"] for s in last5) / len(last5))

    metrics = {
        "total_sessions": len(sessions),
        "work_sessions": len(work_sessions),
        "latest_tests": latest_tests,
        "test_trend": test_trend,
        "avg_quality": avg_quality,
    }

    # Backlog
    backlog_stats = {"total": 0, "done": 0, "remaining": 0}
    bl = ctx.memory_dir / "backlog.md"
    if bl.exists():
        content = bl.read_text(encoding="utf-8")
        checked = len(re.findall(r'- \[x\]', content))
        unchecked = len(re.findall(r'- \[ \]', content))
        backlog_stats = {
            "total": checked + unchecked,
            "done": checked,
            "remaining": unchecked,
        }

    # Features from done.md
    features = []
    done_file = ctx.memory_dir / "done.md"
    if done_file.exists():
        for line in done_file.read_text(encoding="utf-8").splitlines():
            # Extract feature names from done.md format:
            # - **[SESSION #N] Task name** — description
            m = re.match(r'^- \*\*\[SESSION #\d+\]\s*(.+?)\*\*', line)
            if m:
                features.append(m.group(1).strip())

    # Also extract plain-language summaries from work sessions as features
    if not features:
        for s in sessions:
            if s.get("type") == "work" and s.get("summary"):
                features.append(s["summary"])

    # Agents
    agents = list_agents(ctx)

    return {
        "name": name,
        "sessions": sessions,
        "metrics": metrics,
        "backlog": backlog_stats,
        "agents": agents,
        "features": features,
    }


def get_agents_page_data() -> list[dict]:
    """Get all agents across all projects with success rates for the /agents page."""
    try:
        from agency_db_queries import get_top_agents
        return get_top_agents(limit=50)
    except Exception:
        return []


def get_comparison_data() -> list[dict]:
    """Get per-project metrics for the comparison table (3+ projects)."""
    projects = get_projects_data()
    result = []
    for p in projects:
        detail = get_project_detail(p["name"])
        if detail:
            result.append({
                "name": detail["name"],
                "metrics": detail["metrics"],
                "backlog": detail["backlog"],
            })
    return result


def handle_sse(handler, _shutdown_event=None, events_file=None):
    """Handle an SSE connection — stream new events from the JSONL file.

    Args:
        handler: BaseHTTPRequestHandler instance
        _shutdown_event: optional threading.Event for clean test shutdown
        events_file: Path to the JSONL events file. Falls back to SSE_EVENTS_FILE global.
    """
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("Access-Control-Allow-Origin", "http://localhost:8080")
    handler.end_headers()

    if events_file is None:
        events_file = SSE_EVENTS_FILE
    last_pos = 0
    if events_file and events_file.exists():
        last_pos = events_file.stat().st_size

    try:
        while not (_shutdown_event and _shutdown_event.is_set()):
            if events_file and events_file.exists():
                size = events_file.stat().st_size
                if size > last_pos:
                    with open(events_file, "r", encoding="utf-8") as f:
                        f.seek(last_pos)
                        new_data = f.read()
                        last_pos = f.tell()
                    for line in new_data.strip().split("\n"):
                        if line.strip():
                            handler.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                            handler.wfile.flush()
            time.sleep(0.3)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _add_security_headers(handler):
    """Add standard security headers to an HTTP response."""
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Content-Security-Policy",
                        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                        "script-src 'self' 'unsafe-inline'")


def make_handler():
    """Create and return the dashboard HTTP request handler class."""
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                self._route()
            except Exception:
                self.send_response(500)
                _add_security_headers(self)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Internal Server Error")

        def _route(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/events":
                project_name = params.get("project", [None])[0]
                ef = resolve_sse_events_file(project_name)
                if ef is None:
                    self.send_response(400)
                    self.end_headers()
                    return
                handle_sse(self, events_file=ef)
                return

            if parsed.path == "/" or parsed.path == "":
                project = params.get("project", [None])[0]
                if project:
                    detail = get_project_detail(project)
                    if detail:
                        html = render_project_html(detail)
                    else:
                        html = f"<h1>Project '{html_escape(project)}' not found</h1>"
                else:
                    projects = get_projects_data()
                    comparison = ""
                    if len(projects) >= 3:
                        comparison = render_comparison_html(get_comparison_data())
                    html = render_dashboard_html(projects, comparison_html=comparison)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                _add_security_headers(self)
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            elif parsed.path == "/agents":
                agents = get_agents_page_data()
                html = render_agents_html(agents)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                _add_security_headers(self)
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            elif parsed.path == "/spending":
                period = params.get("period", ["month"])[0]
                if period not in ("today", "week", "month"):
                    period = "month"
                html = render_spending_html(period)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                _add_security_headers(self)
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            elif parsed.path == "/health":
                self._json_response(get_health_data())

            elif parsed.path == "/api/projects":
                data = get_projects_data()
                self._json_response(data)

            elif parsed.path.startswith("/api/projects/"):
                name = parsed.path.split("/")[3]
                detail = get_project_detail(name)
                if detail:
                    self._json_response(detail)
                else:
                    self.send_response(404)
                    _add_security_headers(self)
                    self.end_headers()
            else:
                self.send_response(404)
                _add_security_headers(self)
                self.end_headers()

        def _json_response(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "http://localhost:8080")
            _add_security_headers(self)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        def log_message(self, format, *args):
            pass  # quiet

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080):
    """Start the dashboard HTTP server."""
    from http.server import HTTPServer
    server = HTTPServer((host, port), make_handler())
    print(f"\n  [AutoAgent] Dashboard → http://{host}:{port}")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [Dashboard] Stopped.")
        server.server_close()
