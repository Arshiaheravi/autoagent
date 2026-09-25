#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Session helpers: prompt building, agent detection, gates, template syncing."""
import json
import logging
import re
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

from registry import ProjectContext
from orchestrator import parse_agent_hint
from constraint_checker import (
    extract_constraints, extract_all_constraints,
    classify_constraint, check_file_constraints,
)

# ── Backward-compatible re-exports from session_analytics ────
from session_analytics import (  # noqa: F401
    lifetime_cost_summary,
    weekly_cost_summary,
    parse_session_analytics,
    filter_sessions,
    log_session_entry,
    compute_quality_score,
    get_session_type,
    generate_hooks_config,
    generate_hooks_settings_json,
    write_hooks_config,
)


# ── Session timeout guard ────────────────────────────────────
class SessionTimer:
    """Kill a subprocess if it exceeds max_duration seconds."""
    def __init__(self, proc, max_duration, on_timeout=None):
        self.proc = proc
        self.timed_out = False
        def _kill():
            self.timed_out = True
            proc.kill()
            if on_timeout:
                on_timeout()
        self._timer = threading.Timer(max_duration, _kill)
        self._timer.daemon = True

    def start(self):
        self._timer.start()

    def cancel(self):
        self._timer.cancel()


# ── Prompt sanitization ──────────────────────────────────────
_INJECT_RE = re.compile(r'(?i)(ignore\s+(all\s+)?(previous|above|prior)|forget\s+(all|everything)|disregard\s+(all|previous)|new\s+instructions?:|system\s*:|you\s+are\s+now|pretend\s+to\s+be|act\s+as\s+if)')
def _sanitize(text: str) -> str: return _INJECT_RE.sub('[REDACTED]', text)

# ── Build prompt ──────────────────────────────────────────────
def build_prompt(ctx: ProjectContext, session_type: str) -> str:
    def tail(path, chars=1500):
        if not path.exists(): return ""
        raw = path.read_text(encoding="utf-8", errors="replace")[-chars:]
        return _sanitize(raw)

    base = ctx.prompt_file.read_text(encoding="utf-8") if ctx.prompt_file.exists() else ""
    project = ctx.project_file.read_text(encoding="utf-8") if ctx.project_file.exists() else ""

    skills_list = ", ".join(p.name for p in ctx.all_skills())
    quality_summary = ""  # from sessions.json
    if ctx.sessions_file.exists():
        try:
            all_sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
            scored = [s for s in all_sessions if s.get("quality", {}).get("score") is not None]
            if scored:
                last5 = scored[-5:]
                avg = round(sum(s["quality"]["score"] for s in last5) / len(last5))
                quality_summary = f"\n\n## QUALITY SCORES (last {len(last5)} sessions)\nAverage quality score: {avg}/100"
        except Exception:
            pass

    _m = ctx.memory_dir
    memory = (f"\n\n## RECENT SESSIONS\n{tail(_m / 'activity_log.md', 800)}"
        f"\n\n## BACKLOG\n{tail(_m / 'backlog.md', 1200)}"
        f"\n\n## KNOWLEDGE\n{tail(_m / 'knowledge.md', 1500)}{quality_summary}")

    overlay_file = ctx.project_home / "PROMPT_OVERLAY.md"
    overlay = overlay_file.read_text(encoding="utf-8") if overlay_file.exists() else ""
    if session_type == "work":
        skills_note = f"\nAVAILABLE SKILLS: {skills_list}\nRead relevant skill files before starting your task." if skills_list else ""
        return project + "\n\n" + base + "\n\n" + overlay + skills_note + memory

    meta_file = ctx.meta_dir / "PROMPT.md"
    brain_file = ctx.meta_dir / "BRAIN_PROMPT.md"

    if session_type == "meta":
        meta_prompt = meta_file.read_text(encoding="utf-8") if meta_file.exists() else ""
        try:
            from trace_capture import load_last_failed_trace as _lft, format_trace_for_meta as _fmt
            _t = _lft(ctx)
            if _t: memory = f"\n\n## LAST FAILED TRACE\n{_fmt(_t, 1500)}" + memory
        except Exception: pass
        return meta_prompt + memory
    if session_type in ("brain", "deep"):
        brain = brain_file.read_text(encoding="utf-8") if brain_file.exists() else ""
        meta = meta_file.read_text(encoding="utf-8") if meta_file.exists() else ""
        return (brain + "\n\n" + meta + memory) if session_type == "deep" else (brain + memory)

    if session_type == "audit":
        af = ctx.meta_dir / "AUDIT_PROMPT.md"
        return (af.read_text(encoding="utf-8") if af.exists() else "") + memory
    if session_type == "knowledge":
        try: __import__("knowledge_compiler").compile_wiki(ctx)
        except Exception: pass
    return base + memory

# ── Agent detection ─────────────────────────────────────────
def _detect_agent(ctx: ProjectContext, session_type: str) -> str | None:
    if session_type == "audit":
        return "security-auditor" if (ctx.agents_dir / "security-auditor.md").exists() else None
    if session_type not in ("work",): return None
    ct = ctx.memory_dir / "current_task.md"
    if ct.exists():
        m = re.search(r'AGENT:\s*(\S+)', ct.read_text(encoding="utf-8"))
        if m and m.group(1).lower() not in ("(none)", "none"): return m.group(1)
    # Check top backlog task for [agent: X] hint
    bl = ctx.memory_dir / "backlog.md"
    task_text = ""
    if bl.exists():
        for line in bl.read_text(encoding="utf-8").splitlines():
            hint = parse_agent_hint(line)
            if hint:
                agent_file = ctx.agents_dir / f"{hint}.md"
                if agent_file.exists():
                    return hint
                break
            # Capture first task-header line for auto-routing. (Was an
            # unsatisfiable guard — `not startswith("#") and startswith("###")`
            # is never true — which left the auto_route fallback below dead.)
            stripped = line.strip()
            if not task_text and stripped.startswith("###"):
                task_text = stripped

    # Auto-route: match task text against agent keyword index
    if task_text:
        try:
            from agent_index import auto_route
            agent = auto_route(ctx, task_text)
            if agent:
                return agent
        except Exception:
            pass

    return None


# ── Frontend change detection ─────────────────────────────────
_FRONTEND_EXTENSIONS = {".html", ".js", ".css"}


def detect_frontend_changes(events_file: Path) -> bool:
    """Scan emitted events for tool_use actions targeting .html/.js/.css files.

    Returns True if any frontend file was written or edited during the session.
    """
    if not events_file or not events_file.exists():
        return False
    try:
        content = events_file.read_text(encoding="utf-8").strip()
    except Exception:
        return False
    if not content:
        return False
    for line in content.split("\n"):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "tool_use":
            continue
        action = ev.get("action", "")
        if action not in ("writing", "editing"):
            continue
        target = ev.get("target", "")
        if any(target.endswith(ext) for ext in _FRONTEND_EXTENSIONS):
            return True
    return False


# ── Screenshot capture ────────────────────────────────────────
def capture_screenshot(ctx: ProjectContext, session_num: int,
                       url: str | None = None) -> str | None:
    """Capture a screenshot of the project's frontend using playwright.

    Returns the screenshot path relative to project_home, or None if
    playwright is not available or the capture fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    screenshots_dir = ctx.project_home / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    filename = f"session_{session_num}.png"
    filepath = screenshots_dir / filename

    # Default to localhost:8080 (dashboard server) if no URL specified
    target_url = url or "http://127.0.0.1:8080"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(target_url, timeout=10000)
            page.screenshot(path=str(filepath))
            browser.close()
        return f"screenshots/{filename}"
    except Exception:
        return None


# ── Pre-push test gate ────────────────────────────────────────
def _extract_test_command(ctx: ProjectContext) -> str | None:
    """Test command — PROJECT.md `### Test Command` block first, then project.json
    `test_command` (fallback; scaffolded projects only set the config key)."""
    if ctx.project_file.exists():
        content = ctx.project_file.read_text(encoding="utf-8")
        m = re.search(r'###\s*Test Command\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
        if m:
            return m.group(1).strip()
    cfg_cmd = (ctx.config or {}).get("test_command")
    return cfg_cmd.strip() if isinstance(cfg_cmd, str) and cfg_cmd.strip() else None


# Allowlisted runners (shell=False) so a config/PROJECT.md string can't run any binary.
_TEST_RUNNERS = {"pytest", "python", "python3", "npm", "npx", "node", "yarn", "pnpm",
                 "cargo", "go", "make", "poetry", "uv", "bundle", "rspec", "dotnet",
                 "mvn", "gradle", "deno", "jest", "vitest", "tox", "rake", "phpunit"}


def _pre_push_gate(ctx: ProjectContext, session_num: int = 0) -> bool:
    """Run the project's tests. True if they pass (or the gate can't run the
    command), False if they fail. Unrunnable commands are SKIPPED but LOGGED."""
    import shlex
    test_cmd = _extract_test_command(ctx)
    if not test_cmd:
        return True
    stripped = test_cmd.strip()
    first_word = stripped.split()[0] if stripped else ""
    if any(op in stripped for op in ("&&", "||", "|", ";", "`", "$(")) or first_word not in _TEST_RUNNERS:
        logger.warning("[pre-push gate] SKIPPED for %s — cannot run %r shell-free; "
                       "simplify to one allowlisted test runner to enable it.", ctx.name, test_cmd)
        return True
    try:
        result = subprocess.run(shlex.split(test_cmd), shell=False, cwd=str(ctx.project_root),
                                capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning("[pre-push gate] timed out for %s", ctx.name)
        return False
    except Exception as e:
        logger.warning("[pre-push gate] SKIPPED for %s — %r failed: %s", ctx.name, test_cmd, e)
        return True


# ── Constraint gate ───────────────────────────────────────────
def _constraint_gate(ctx: ProjectContext) -> list[dict]:
    """Extract NEVER/ALWAYS/MUST constraints from project .md files and check
    changed files against file-pattern constraints.

    Returns list of violation dicts (empty = pass).
    """
    all_rules = []
    for md_file in [ctx.prompt_file, ctx.project_file]:
        if md_file and md_file.exists():
            all_rules.extend(extract_constraints(md_file))

    skills_dir = ctx.project_home / "skills"
    if skills_dir.exists():
        all_rules.extend(extract_all_constraints(skills_dir))

    if not all_rules:
        return []

    classified = [classify_constraint(r) for r in all_rules]
    file_rules = [r for r in classified if r.get("type") == "file_pattern"]

    if not file_rules:
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(ctx.project_root), capture_output=True, text=True, timeout=30,
        )
        changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []  # can't determine changed files — don't block

    return check_file_constraints(file_rules, changed)


# ── Template syncing ──────────────────────────────────────────
def _sync_templates(ctx: ProjectContext):
    """Copy shared templates into project_home so the .autoagent symlink exposes them.
    Project-specific files always take precedence (are not overwritten)."""
    import shutil as _sh
    templates = ctx.agency_home / "templates"

    # PROMPT.md → project_home/PROMPT.md (only if no project-specific override)
    for fname in ["PROMPT.md"]:
        src = templates / fname
        dst = ctx.project_home / fname
        if src.exists() and not dst.exists():
            _sh.copy2(src, dst)

    # meta/ directory
    meta_src = templates / "meta"
    meta_dst = ctx.project_home / "meta"
    if meta_src.exists():
        meta_dst.mkdir(exist_ok=True)
        for f in meta_src.glob("*.md"):
            dst = meta_dst / f.name
            if not dst.exists():
                _sh.copy2(f, dst)

    # Merge skills: shared → project_home/skills/ — but SKIP project-domain skills
    # this project hasn't enabled. Copying them in would make them permanently
    # visible (project-local always overrides scoping), leaking one client's
    # domain skills into another's project.
    shared_skills = ctx.agency_home / "skills"
    project_skills = ctx.project_home / "skills"
    project_skills.mkdir(exist_ok=True)
    if shared_skills.exists():
        try:
            from org_model import hidden_project_domain_skills
            hidden = hidden_project_domain_skills(ctx)
        except Exception:
            hidden = set()
        for f in shared_skills.glob("*.md"):
            if f.stem in hidden:
                continue
            dst = project_skills / f.name
            if not dst.exists():
                _sh.copy2(f, dst)
