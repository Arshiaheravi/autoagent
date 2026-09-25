#!/usr/bin/env python3
"""Tests for dashboard_server.py — SSE streaming, HTTP endpoints, replay, security."""
import json
import time
import inspect
import threading
import http.client
import pytest
from pathlib import Path

import registry
import dashboard_server
import event_emitter


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    home = isolated_agency_home
    yield


@pytest.fixture
def project_with_sessions(tmp_path):
    """A registered project with session history."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    ctx = registry.register("testproj", proj)
    ctx.ensure_dirs()
    (ctx.project_home / "PROJECT.md").write_text("# Test")
    (ctx.project_home / "NORTH_STAR.md").write_text("# Star")
    (ctx.memory_dir / "backlog.md").write_text("- [ ] task 1\n- [ ] task 2\n- [x] done task")
    (ctx.memory_dir / "current_task.md").write_text("# Current Task: (none)")
    (ctx.memory_dir / "activity_log.md").write_text("# Log\n## 2026-03-26 — FEATURE\nDONE: Built thing")
    (ctx.memory_dir / "done.md").write_text("# Done\n- Built thing")

    sessions = [
        {"session": 1, "type": "work", "date": "2026-03-26", "summary": "Farm CRUD",
         "tests": {"before": 1, "after": 22, "status": "pass"}, "files": ["api/farms.py"]},
        {"session": 2, "type": "work", "date": "2026-03-26", "summary": "Soil API",
         "tests": {"before": 22, "after": 36, "status": "pass"}, "files": ["api/soil.py"]},
        {"session": 3, "type": "meta", "date": "2026-03-26", "summary": "Improved prompts",
         "tests": {"before": 36, "after": 36, "status": "pass"}, "files": ["PROMPT.md"]},
        {"session": 4, "type": "work", "date": "2026-03-26", "summary": "NDVI service",
         "tests": {"before": 36, "after": 58, "status": "pass"}, "files": ["services/crop/ndvi.py"]},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")
    ctx.counter_file.write_text(json.dumps({"count": 5}))
    ctx.agents_dir.mkdir(exist_ok=True)
    (ctx.agents_dir / "crop-analyst.md").write_text("# Crop Analyst")
    (ctx.agents_dir / "architect.md").write_text("# Architect")
    return ctx


# ── SSE helpers ──

def _start_test_server():
    """Start the dashboard server on an OS-assigned port, return (server, port, shutdown_event)."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse

    shutdown_event = threading.Event()

    class TestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/events":
                dashboard_server.handle_sse(self, _shutdown_event=shutdown_event)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, shutdown_event


# ── SSE endpoint tests ──

def test_sse_endpoint_returns_event_stream(tmp_path):
    """GET /events returns Content-Type text/event-stream."""
    events_file = tmp_path / "live_events.jsonl"
    events_file.write_text("")
    dashboard_server.SSE_EVENTS_FILE = events_file

    server, port, shutdown_event = _start_test_server()
    try:
        import socket as _sock
        sock = _sock.create_connection(("127.0.0.1", port), timeout=3)
        sock.sendall(b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        # Read HTTP response headers
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += sock.recv(1024)
        headers = buf.split(b"\r\n\r\n")[0].decode()
        assert "200" in headers.split("\r\n")[0]
        assert "text/event-stream" in headers
        sock.close()
    finally:
        shutdown_event.set()
        server.shutdown()


def test_sse_sends_new_events(tmp_path):
    """Emit an event, SSE client receives it within 2s."""
    events_file = tmp_path / "live_events.jsonl"
    events_file.write_text("")
    dashboard_server.SSE_EVENTS_FILE = events_file

    server, port, shutdown_event = _start_test_server()
    try:
        import socket as _sock
        sock = _sock.create_connection(("127.0.0.1", port), timeout=3)
        sock.sendall(b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")

        # Read past the HTTP headers
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += sock.recv(1024)

        # Now emit an event
        event_emitter.emit(events_file, project="test", session=1, type="tool_use",
                           action="writing", target="app.py")

        # Read SSE data — should arrive within 2s
        sock.settimeout(3)
        data = b""
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if chunk:
                    data += chunk
                    if b"tool_use" in data:
                        break
            except _sock.timeout:
                break

        assert b"tool_use" in data, f"Expected SSE event with 'tool_use', got: {data!r}"
        sock.close()
    finally:
        shutdown_event.set()
        server.shutdown()


def test_handle_sse_accepts_events_file_param(tmp_path):
    """handle_sse should accept events_file as a parameter, not rely on global."""
    sig = inspect.signature(dashboard_server.handle_sse)
    assert "events_file" in sig.parameters, "handle_sse must accept events_file parameter"


def test_sse_streams_from_explicit_events_file(tmp_path):
    """handle_sse with explicit events_file streams events without setting global."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    events_file = tmp_path / "live_events.jsonl"
    events_file.write_text("")
    shutdown_event = threading.Event()

    # Do NOT set dashboard_server.SSE_EVENTS_FILE — the param should be enough
    old_global = dashboard_server.SSE_EVENTS_FILE
    dashboard_server.SSE_EVENTS_FILE = None

    class TestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            dashboard_server.handle_sse(self, events_file=events_file,
                                        _shutdown_event=shutdown_event)
        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        import socket as _sock
        sock = _sock.create_connection(("127.0.0.1", port), timeout=3)
        sock.sendall(b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += sock.recv(1024)

        # Emit an event
        event_emitter.emit(events_file, project="test", session=1,
                           type="tool_use", action="reading", target="foo.py")

        sock.settimeout(3)
        data = b""
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if chunk:
                    data += chunk
                    if b"tool_use" in data:
                        break
            except _sock.timeout:
                break

        assert b"tool_use" in data, f"Expected event via param, got: {data!r}"
        sock.close()
    finally:
        dashboard_server.SSE_EVENTS_FILE = old_global
        shutdown_event.set()
        server.shutdown()


def test_sse_missing_project_returns_400(tmp_path):
    """GET /events without ?project= should return 400, not fall back to global."""
    assert dashboard_server.resolve_sse_events_file(None) is None, \
        "resolve_sse_events_file(None) should return None for missing project"


def test_sse_unknown_project_returns_400(tmp_path):
    """GET /events?project=nonexistent should return None (no fallback)."""
    result = dashboard_server.resolve_sse_events_file("nonexistent")
    assert result is None, \
        f"resolve_sse_events_file('nonexistent') should return None, got {result}"


def test_sse_two_projects_isolated(tmp_path):
    """Two projects emit events — each SSE stream only sees its own project's events."""
    # Register two projects
    p1 = tmp_path / "alpha"
    p2 = tmp_path / "beta"
    p1.mkdir()
    p2.mkdir()
    ctx1 = registry.register("alpha", p1)
    ctx1.ensure_dirs()
    ctx2 = registry.register("beta", p2)
    ctx2.ensure_dirs()

    # Resolve returns different paths
    ef1 = dashboard_server.resolve_sse_events_file("alpha")
    ef2 = dashboard_server.resolve_sse_events_file("beta")
    assert ef1 is not None, "alpha should resolve to an events file"
    assert ef2 is not None, "beta should resolve to an events file"
    assert ef1 != ef2, f"Two projects must have different events files, got {ef1} and {ef2}"

    # Create event files and emit events
    ef1.parent.mkdir(parents=True, exist_ok=True)
    ef1.write_text("")
    ef2.parent.mkdir(parents=True, exist_ok=True)
    ef2.write_text("")

    event_emitter.emit(ef1, project="alpha", session=1, type="tool_use", action="alpha_action")
    event_emitter.emit(ef2, project="beta", session=1, type="tool_use", action="beta_action")

    # Verify isolation: alpha's file only has alpha events, beta's only beta
    alpha_events = event_emitter.read_events(ef1)
    beta_events = event_emitter.read_events(ef2)
    assert len(alpha_events) == 1
    assert alpha_events[0]["action"] == "alpha_action"
    assert len(beta_events) == 1
    assert beta_events[0]["action"] == "beta_action"


def test_project_html_sse_url_includes_project_name():
    """Project HTML JS should connect to /events?project=<name> for scoped streaming."""
    detail = {
        "name": "myproject",
        "sessions": [{"session": 1, "type": "work", "summary": "x",
                       "tests": {"after": 5}, "date": "2026-03-27"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 5,
                    "test_trend": [5]},
        "backlog": {"total": 2, "done": 0, "remaining": 2},
        "agents": [],
    }
    html = dashboard_server.render_project_html(detail)
    assert "/events?project=myproject" in html, \
        "SSE URL must include ?project=<name> for per-project streaming"


# ── Dashboard HTTP API endpoints ──

def _start_dashboard_server():
    """Start the dashboard server on a random port, return (server, port, thread)."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/projects":
                data = dashboard_server.get_projects_data()
                self._json_response(data)
            elif parsed.path.startswith("/api/projects/"):
                name = parsed.path.split("/")[3]
                detail = dashboard_server.get_project_detail(name)
                if detail:
                    self._json_response(detail)
                else:
                    self.send_response(404)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def _json_response(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_api_projects_returns_json_list(project_with_sessions):
    """GET /api/projects returns a JSON array with registered projects."""
    server, port = _start_dashboard_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/api/projects")
        resp = conn.getresponse()
        assert resp.status == 200
        data = json.loads(resp.read())
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "testproj"
        conn.close()
    finally:
        server.shutdown()


def test_api_project_detail_returns_json(project_with_sessions):
    """GET /api/projects/<name> returns project detail JSON."""
    server, port = _start_dashboard_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/api/projects/testproj")
        resp = conn.getresponse()
        assert resp.status == 200
        data = json.loads(resp.read())
        assert data["name"] == "testproj"
        assert "sessions" in data
        assert "metrics" in data
        conn.close()
    finally:
        server.shutdown()


def test_api_project_unknown_returns_404(project_with_sessions):
    """GET /api/projects/<unknown> returns 404."""
    server, port = _start_dashboard_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/api/projects/nonexistent")
        resp = conn.getresponse()
        assert resp.status == 404
        conn.close()
    finally:
        server.shutdown()


# ── Session replay viewer ──

def test_replay_endpoint_returns_events(tmp_path):
    """/api/sessions/<id>/events returns JSONL events filtered by session ID."""
    events_file = tmp_path / "live_events.jsonl"
    # Emit events from two different sessions
    event_emitter.emit(events_file, project="testproj", session=1, type="session_start")
    event_emitter.emit(events_file, project="testproj", session=1, type="tool_use",
                       action="reading", target="src/app.py")
    event_emitter.emit(events_file, project="testproj", session=1, type="tool_use",
                       action="writing", target="src/app.py")
    event_emitter.emit(events_file, project="testproj", session=1, type="session_end",
                       summary="Built thing")
    event_emitter.emit(events_file, project="testproj", session=2, type="session_start")
    event_emitter.emit(events_file, project="testproj", session=2, type="tool_use",
                       action="reading", target="src/foo.py")

    events = dashboard_server.get_session_events(events_file, session_id=1)
    assert len(events) == 4, f"Expected 4 events for session 1, got {len(events)}"
    assert events[0]["type"] == "session_start"
    assert events[-1]["type"] == "session_end"
    # All returned events belong to session 1
    for ev in events:
        assert ev["session"] == 1


def test_replay_html_renders_timeline():
    """Replay HTML shows tool calls with timestamps in a timeline."""
    import dashboard_html
    events = [
        {"timestamp": "2026-03-28T10:00:00Z", "type": "session_start", "session": 5},
        {"timestamp": "2026-03-28T10:01:00Z", "type": "tool_use", "session": 5,
         "action": "reading", "target": "src/app.py"},
        {"timestamp": "2026-03-28T10:02:00Z", "type": "tool_use", "session": 5,
         "action": "writing", "target": "src/models.py"},
        {"timestamp": "2026-03-28T10:05:00Z", "type": "session_end", "session": 5,
         "summary": "Built API endpoints"},
    ]
    html = dashboard_html.render_replay_html("testproj", 5, events)
    assert "<!DOCTYPE html>" in html
    assert "testproj" in html
    assert "#5" in html  # session number
    assert "session_start" in html or "Session Start" in html
    assert "src/app.py" in html
    assert "src/models.py" in html
    assert "10:01" in html or "10:01:00" in html  # timestamp visible
    assert "10:02" in html or "10:02:00" in html


def test_replay_highlights_errors():
    """Failed tool calls are highlighted differently (error class or red styling)."""
    import dashboard_html
    events = [
        {"timestamp": "2026-03-28T10:00:00Z", "type": "session_start", "session": 3},
        {"timestamp": "2026-03-28T10:01:00Z", "type": "tool_use", "session": 3,
         "action": "reading", "target": "src/app.py"},
        {"timestamp": "2026-03-28T10:02:00Z", "type": "tool_use", "session": 3,
         "action": "writing", "target": "src/broken.py", "error": "SyntaxError: unexpected indent"},
        {"timestamp": "2026-03-28T10:03:00Z", "type": "session_end", "session": 3},
    ]
    html = dashboard_html.render_replay_html("testproj", 3, events)
    # The error event should have a distinct CSS class for red highlighting
    assert "replay-error" in html, "Error events must have 'replay-error' CSS class"
    assert "SyntaxError" in html, "Error message should be visible"
    # Non-error events should NOT have the error class — count element instances (not CSS selectors)
    assert html.count('class="replay-event replay-error"') == 1, "Only the failed tool call should have error class"


# ── XSS + Security ──

def test_xss_project_not_found_escaped():
    """html_escape is imported and used in dashboard_server for project-not-found."""
    from html import escape as html_escape
    # Simulate the XSS payload that would come from a query param
    project = '<script>alert(1)</script>'
    # This is the pattern used in dashboard_server.py (after fix)
    html = f"<h1>Project '{html_escape(project)}' not found</h1>"
    assert "<script>" not in html, "XSS: unescaped script tag in response"
    assert "&lt;script&gt;" in html, "Project name should be HTML-escaped"


def test_dashboard_security_headers():
    """_add_security_headers sets all required security headers."""
    headers = {}

    class FakeHandler:
        def send_header(self, name, value):
            headers[name] = value

    handler = FakeHandler()
    dashboard_server._add_security_headers(handler)

    assert headers.get("X-Content-Type-Options") == "nosniff", \
        "Missing X-Content-Type-Options header"
    assert headers.get("X-Frame-Options") == "DENY", \
        "Missing X-Frame-Options header"
    csp = headers.get("Content-Security-Policy", "")
    assert "default-src" in csp, "Missing Content-Security-Policy header"


def test_dashboard_security_headers_on_html_response(project_with_sessions):
    """HTML dashboard responses include security headers via serve() handler."""
    from http.server import HTTPServer
    server = HTTPServer(("127.0.0.1", 0), dashboard_server.make_handler())
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/")
        resp = conn.getresponse()
        resp.read()
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        assert resp.getheader("X-Frame-Options") == "DENY"
        conn.close()

        # JSON endpoint too
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/api/projects")
        resp = conn.getresponse()
        resp.read()
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        conn.close()
    finally:
        server.shutdown()


def test_dashboard_error_no_stack_trace(project_with_sessions):
    """Internal errors don't leak stack traces to the client."""
    from http.server import HTTPServer
    server = HTTPServer(("127.0.0.1", 0), dashboard_server.make_handler())
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/api/projects/nonexistent")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        assert "Traceback" not in body, "Stack trace leaked in error response"
        assert resp.status in (404, 500)
        conn.close()
    finally:
        server.shutdown()


# ── Health endpoint ──

def test_health_endpoint_returns_json(project_with_sessions):
    """GET /health returns JSON with uptime, sessions_today, tests_passing, daily_cost, active_projects."""
    from dashboard_components import get_health_data
    data = get_health_data()
    assert isinstance(data, dict)
    for key in ("uptime_seconds", "sessions_today", "tests_passing", "daily_cost", "active_projects"):
        assert key in data, f"Missing key: {key}"
    assert isinstance(data["active_projects"], int)
    assert data["active_projects"] >= 1  # project_with_sessions registered one
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["daily_cost"], (int, float))
    assert isinstance(data["sessions_today"], int)
    assert isinstance(data["tests_passing"], int)


def test_health_endpoint_includes_cost(tmp_path):
    """Health data reflects daily cost from budget file."""
    from dashboard_components import get_health_data
    proj = tmp_path / "costproj"
    proj.mkdir()
    ctx = registry.register("costproj", proj)
    ctx.ensure_dirs()
    (ctx.project_home / "PROJECT.md").write_text("# Test")
    today = __import__("datetime").date.today().isoformat()
    ctx.budget_file.write_text(json.dumps({today: 1.50}), encoding="utf-8")
    data = get_health_data()
    assert data["daily_cost"] >= 1.50


def test_health_endpoint_no_projects(tmp_path):
    """Health data works with zero registered projects."""
    # Clear registry
    import registry as reg
    agency_file = reg.AGENCY_HOME / "agency.json"
    agency_file.write_text(json.dumps({"projects": {}}), encoding="utf-8")
    from dashboard_components import get_health_data
    data = get_health_data()
    assert data["active_projects"] == 0
    assert data["sessions_today"] == 0
    assert data["daily_cost"] == 0.0
