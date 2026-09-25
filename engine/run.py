#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoAgent Agency — Multi-Project Autonomous Agent Engine."""
import io, json, logging, os, shutil, subprocess, sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from registry import ProjectContext, AGENCY_HOME
from orchestrator import build_agent_boot_prompt, list_agents
from event_emitter import emit as emit_event
from session_helpers import (
    compute_quality_score, get_session_type, build_prompt,
    detect_frontend_changes, capture_screenshot,
    _detect_agent, _extract_test_command, _pre_push_gate,
    _constraint_gate, _sync_templates, parse_session_analytics,
    generate_hooks_settings_json, lifetime_cost_summary, weekly_cost_summary,
    log_session_entry, SessionTimer,
)
from integrity import lock_ctx_instruction_files, unlock_ctx_instruction_files, snapshot_critical, check_integrity
from models import DEFAULT_DAILY_LIMIT_USD

def _find_claude() -> str:
    found = shutil.which("claude")
    if found: return found
    if sys.platform == "win32":
        p = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
        if os.path.exists(p): return p
    return "claude"

CLAUDE = _find_claude()


def _scope_index_text(text: str, ctx) -> str:
    """Strip the fenced project-domain block from INDEX.md unless this project
    enables project-domain skills, so a generic tenant's system prompt never
    carries another client's routing rows."""
    import re
    try:
        from org_model import project_domain_enabled
        if project_domain_enabled(ctx):
            return text
    except Exception:
        pass  # fail closed: strip the project-domain block
    stripped = re.sub(
        r"\n?<!-- PROJECT-DOMAIN-START.*?PROJECT-DOMAIN-END -->\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )
    return stripped.rstrip() + "\n"


# ── Budget ─────────────────────────────────────────────────────
def budget_ok(ctx: ProjectContext) -> bool:
    today = str(date.today())
    limit = ctx.config.get("daily_limit_usd", DEFAULT_DAILY_LIMIT_USD)
    if not ctx.budget_file.exists():
        return True
    try:
        data = json.loads(ctx.budget_file.read_text())
        return data.get(today, 0.0) < limit
    except Exception:
        return True

def log_cost(ctx: ProjectContext, usd: float):
    today = str(date.today())
    data = {}
    if ctx.budget_file.exists():
        try: data = json.loads(ctx.budget_file.read_text())
        except Exception: pass
    data[today] = round(data.get(today, 0.0) + usd, 4)
    ctx.budget_file.write_text(json.dumps(data, indent=2))


def _iso_week() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"


def weekly_session_ok(ctx: ProjectContext) -> bool:
    """False once this ISO week's launched-session count hits weekly_session_budget.
    Guards a tenant's Claude (Max) weekly quota so autoagent can't starve their own
    interactive use. Unset / 0 = unlimited."""
    budget = ctx.config.get("weekly_session_budget")
    if not budget:
        return True
    wf = ctx.weekly_sessions_file
    if not wf.exists():
        return True
    try:
        data = json.loads(wf.read_text())
        return data.get(_iso_week(), 0) < int(budget)
    except Exception:
        return True


def log_session(ctx: ProjectContext):
    """Count one launched session against the current ISO week."""
    wf = ctx.weekly_sessions_file
    data = {}
    if wf.exists():
        try: data = json.loads(wf.read_text())
        except Exception: pass
    key = _iso_week()
    data[key] = data.get(key, 0) + 1
    wf.write_text(json.dumps(data, indent=2))


def _log_knowledge(ctx: ProjectContext, entry: str):
    kf = ctx.memory_dir / "knowledge.md"
    existing = kf.read_text(encoding="utf-8") if kf.exists() else ""
    kf.write_text(existing + entry, encoding="utf-8")


def _write_sigint_checkpoint(ctx: ProjectContext, session_num: int, session_type: str):
    """Bug-3 fix: on SIGINT, the Claude CLI subprocess is killed before the
    agent reaches its step-8 reflexion write. Salvage what we can by
    extracting the last ~25 tool calls from live_events.jsonl and writing
    a breadcrumb stub to knowledge.md so the next session can resume.

    Idempotent — re-running an interrupted session reads this stub via the
    knowledge.md tail in build_prompt and knows to pick up mid-task instead
    of starting from scratch.
    """
    events_file = ctx.project_home / "live_events.jsonl"
    last_events: list[dict] = []
    if events_file.exists():
        try:
            with open(events_file, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()[-25:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    last_events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass

    session_events = [e for e in last_events if e.get("session") == session_num]
    if not session_events:
        session_events = last_events

    bullets: list[str] = []
    for e in session_events[-15:]:
        tool = e.get("tool", "?")
        action = e.get("action", "?")
        target = (e.get("target") or "")[:120]
        if tool and tool != "?":
            bullets.append(f"  - {tool}/{action} → {target}".rstrip())

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    stub = (
        f"\n### Session #{session_num} INTERRUPTED — {ts}\n"
        f"INTERRUPTED: SIGINT before reflexion was written. "
        f"Session type: {session_type}. Last {len(bullets)} tool calls captured below. "
        f"Next session should read current_task.md + this trail to decide whether to resume or restart.\n"
        f"\n#### Last tool calls before interrupt\n"
    )
    if bullets:
        stub += "\n".join(bullets) + "\n"
    else:
        stub += "  - (no events captured in live_events.jsonl)\n"
    stub += (
        f"\n**For the next session:** check `git status` first — if files were modified mid-flight, "
        f"the work may be partially done. Verify via `git diff` (not `git status`) which files actually "
        f"changed. Then decide whether to commit-as-is, finish the partial work, or revert and restart.\n"
    )
    _log_knowledge(ctx, stub)
    print(f"  [AutoAgent] SIGINT checkpoint written to knowledge.md ({len(bullets)} tool calls captured)")


def _extract_stream_error_text(event: dict) -> str:
    """Flatten non-assistant stream-json events into searchable text."""
    parts: list[str] = []

    def _walk(value):
        if isinstance(value, str):
            text = " ".join(value.split())
            if text and text not in parts:
                parts.append(text)
            return
        if isinstance(value, list):
            for item in value:
                _walk(item)
            return
        if isinstance(value, dict):
            for key in ("error", "message", "text", "detail", "details", "reason", "content", "status"):
                if key in value:
                    _walk(value[key])

    _walk(event)
    return " | ".join(parts[:8])


# ── Run one session ────────────────────────────────────────────
_SENTINEL = object()  # distinguishes "no override" from "explicitly generic (None)"


def _vault_byok_key() -> Optional[str]:
    """Tenant BYOK key from the encrypted vault (Phase 3); None unless
    AUTOAGENT_VAULT_KEY set AND tenant has a vault, else config/env as before."""
    if not os.environ.get("AUTOAGENT_VAULT_KEY"):
        return None
    try:
        import vault; from tenant import current_tenant
    except ImportError:
        return None
    # Let InvalidToken PROPAGATE — falling back to the operator key on a bad decrypt
    # would run the session as the wrong identity. Absent secret => None.
    return vault.get_secret(current_tenant().tenant_id, "ANTHROPIC_API_KEY")


def _build_child_env(ctx: ProjectContext) -> dict:
    """Build the subprocess env for the claude CLI (BYOK-aware): inject the tenant
    key (vault > config > $BYOK_ANTHROPIC_API_KEY) so it bills the tenant, else
    STRIP ANTHROPIC_API_KEY so a dead shell key can't force CLI API-mode."""
    child_env = os.environ.copy()
    byok_key = (_vault_byok_key()
                or ctx.config.get("anthropic_api_key")
                or os.environ.get("BYOK_ANTHROPIC_API_KEY"))
    if byok_key:
        child_env["ANTHROPIC_API_KEY"] = str(byok_key)
    else:
        child_env.pop("ANTHROPIC_API_KEY", None)
    return child_env


def run_session(ctx: ProjectContext, session_type: str, session_num: int,
                agent_override=_SENTINEL, worktree_dir=None) -> bool:
    """Run a single agent session."""
    if not (shutil.which(CLAUDE) or os.path.exists(CLAUDE)):
        print("  [AutoAgent] Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code")
        return False

    # Pre-session cost prediction — warn if likely to exceed budget
    try:
        from cost_predictor import predict_session_cost
        forecast = predict_session_cost(ctx, session_type)
        if forecast["recommend"] == "skip":
            print(f"  [AutoAgent] BUDGET WARNING: {forecast['reason']}")
    except Exception:
        pass

    # Integrity baseline — snapshot critical files before session
    try: integrity_baseline = snapshot_critical(ctx)
    except Exception: integrity_baseline = {}

    prompt = build_prompt(ctx, session_type)

    # Detect agent: use override if provided, otherwise auto-detect
    agent_name = agent_override if agent_override is not _SENTINEL else _detect_agent(ctx, session_type)
    # Success-rate routing: swap underperforming agents
    try:
        if agent_name and agent_override is _SENTINEL:
            from agent_router import maybe_swap_agent
            agent_name = maybe_swap_agent(ctx.name, agent_name, session_type, ctx.agents_dir)
    except Exception: pass
    agent_label = f" [{agent_name}]" if agent_name else ""
    wt_label = f" [worktree]" if worktree_dir else ""
    print(f"\n  [AutoAgent] Session #{session_num} — {session_type.upper()}{agent_label}{wt_label} — {ctx.name} — {datetime.now().strftime('%H:%M')}")

    try: from features import maybe_ultraplan; maybe_ultraplan(ctx, session_type)
    except Exception: pass

    # Build agent-scoped boot prompt
    boot_prompt = build_agent_boot_prompt(ctx, agent_name, session_type)

    # Ensure PROMPT.md is accessible via symlink
    _sync_templates(ctx)

    # Hooks delivered inline via `claude --settings` (claude_args) — load even
    # when project root is read-only (sandbox/worktree); no settings file write.

    # Interactive planning: propose plan for review before session starts
    try:
        from comms_handlers import propose_plan
        propose_plan(ctx.memory_dir / "current_task.md", project=ctx.name)
    except Exception: pass

    # Emit session_start event for live dashboard
    ef = ctx.events_file
    emit_event(ef, project=ctx.name, session=session_num, type="session_start",
               session_type=session_type, agent=agent_name)

    # Frustration detection + trace capture
    try:
        from features import FrustrationDetector, get_flag
        frustration = FrustrationDetector() if get_flag(ctx, "frustration") else None
    except Exception: frustration = None
    try:
        from trace_capture import SessionTracer
        tracer = SessionTracer(ctx, session_num, agent=agent_name or "")
    except Exception: tracer = None
    locked = False
    if session_type == "work":
        try: lock_ctx_instruction_files(ctx); locked = True
        except Exception: pass

    proc = None
    _fallback_hints: list[str] = []
    mode = ctx.config.get("mode", "cli")
    run_cwd = str(worktree_dir) if worktree_dir else str(ctx.project_root)

    # Bug-3 fix (signal-propagation half): install an explicit Python SIGINT
    # handler so the stdin/stdout read loop reliably interrupts to the
    # KeyboardInterrupt handler below. Without this, SIGINT to the parent
    # often also reaches the Claude CLI child, which closes stdout cleanly,
    # the read loop returns normally, and the KeyboardInterrupt path
    # (where the checkpoint is written) never fires.
    import signal as _signal
    _sigint_caught = [False]
    _prev_sigint = _signal.getsignal(_signal.SIGINT)

    def _on_sigint(_sig, _frame):
        _sigint_caught[0] = True
        raise KeyboardInterrupt
    try:
        _signal.signal(_signal.SIGINT, _on_sigint)
    except (ValueError, OSError):
        pass

    # BYOK-aware subprocess env: inject the tenant key when configured, else strip
    # ANTHROPIC_API_KEY so a dead shell key can't force CLI API-mode. See _build_child_env.
    child_env = _build_child_env(ctx)

    # Model routing by session_type — config models.{type} → config model →
    # the models.py tier default (SSoT). Always resolves to a real id.
    from models import resolve_model
    model_for_session = resolve_model(ctx.config, session_type)
    claude_args = [CLAUDE, "-p", boot_prompt,
                   "--output-format", "stream-json",
                   "--verbose",
                   "--dangerously-skip-permissions",
                   "--max-turns", str(ctx.config.get("session_max_turns", 50)),
                   "--settings", generate_hooks_settings_json(ctx),
                   "--exclude-dynamic-system-prompt-sections"]
    if model_for_session:
        claude_args.extend(["--model", model_for_session])

    # Prompt caching: stable ~6-10k tokens of project rules go into the system
    # prompt so identical content hashes identically across sessions and hits
    # Anthropic's 5-min prompt-cache TTL on back-to-back runs.
    try:
        stable_parts: list[str] = []
        for label, path in (
            ("PROMPT", ctx.project_home / "PROMPT.md"),
            ("PROJECT", ctx.project_file),
            ("NORTH_STAR", ctx.north_star_file),
        ):
            if path.exists():
                try:
                    stable_parts.append(f"\n\n<<{label}>>\n{path.read_text(encoding='utf-8')}")
                except Exception:
                    continue
        injected_skills: set[str] = set()
        for skills_dir in ctx.skills_dirs():
            for name in ("INDEX.md", "agent-patterns.md"):
                if name in injected_skills:
                    continue
                sp = skills_dir / name
                if sp.exists():
                    try:
                        text = sp.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    if name == "INDEX.md":
                        text = _scope_index_text(text, ctx)
                    stable_parts.append(f"\n\n<<SKILL:{name}>>\n{text}")
                    injected_skills.add(name)
        system_prompt = "".join(stable_parts).strip()
        if system_prompt:
            claude_args.extend(["--append-system-prompt", system_prompt])
    except Exception as e:
        logger.debug("prompt caching setup skipped: %s", e)

    session_cost_usd = 0.0
    # Execution sandbox (Fork A): LocalRunner default (unchanged) or ContainerRunner.
    from sandbox import get_runner
    launch_argv, launch_kwargs = get_runner(ctx).wrap(claude_args, run_cwd, child_env)
    try:
        proc = subprocess.Popen(
            launch_argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            **launch_kwargs,
        )
        max_dur = ctx.config.get("session_max_duration", ctx.config.get("session_max_seconds", 1800))
        stimer = SessionTimer(proc, max_dur)
        stimer.start()
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw: continue
            try:
                ev = json.loads(raw)
                t = ev.get("type", "")
                if t == "assistant":
                    for block in ev.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            text_out = block["text"].strip()
                            print(text_out, flush=True)
                            _fallback_hints.append(text_out)
                            if frustration: frustration.observe_text(text_out)
                            if tracer: tracer.record_text(text_out)
                        elif block.get("type") == "tool_use":
                            inp = block.get("input", {})
                            name = block.get("name", "")
                            if name == "Read":
                                action, target = "reading", inp.get("file_path", "")
                                print(f"  → reading {target}", flush=True)
                            elif name == "Write":
                                action, target = "writing", inp.get("file_path", "")
                                print(f"  → writing {target}", flush=True)
                            elif name == "Bash":
                                action, target = "running", str(inp.get("command", ""))[:80]
                                print(f"  → running: {target}", flush=True)
                            elif name == "Edit":
                                action, target = "editing", inp.get("file_path", "")
                                print(f"  → editing {target}", flush=True)
                            else:
                                action, target = name.lower(), ""
                                print(f"  → {name}", flush=True)
                            emit_event(ef, project=ctx.name, session=session_num,
                                       type="tool_use", tool=name, action=action, target=target)
                            if frustration: frustration.observe_tool(name, target)
                            if tracer: tracer.record_tool_call(name, inp)
                elif t == "result":
                    # Track token usage for all modes
                    try:
                        from usage import record_session_usage, format_tokens
                        record_session_usage(ctx, ev)
                        total = ev.get("usage", {}).get("output_tokens", 0)
                        total += ev.get("usage", {}).get("input_tokens", 0)
                        cost = ev.get("total_cost_usd", 0.0)
                        dur = ev.get("duration_ms", 0)
                        print(
                            f"\n  [Session complete] "
                            f"{format_tokens(total)} tokens | "
                            f"${cost:.4f} | "
                            f"{dur // 1000}s",
                            flush=True,
                        )
                    except Exception:
                        print(f"\n  [Session complete]", flush=True)
                    result_cost = ev.get("cost_usd") or ev.get("total_cost_usd") or 0.0
                    if isinstance(result_cost, (int, float)) and result_cost > 0:
                        session_cost_usd = float(result_cost)
                        if mode == "api":
                            log_cost(ctx, result_cost)
                else:
                    error_text = _extract_stream_error_text(ev)
                    if error_text:
                        print(f"  [Claude {t or 'event'}] {error_text}", flush=True)
                        _fallback_hints.append(error_text)
            except Exception:
                if raw and not raw.startswith("{"):
                    print(raw, flush=True)
                    _fallback_hints.append(raw)
        proc.wait()
        stimer.cancel()
        if stimer.timed_out:
            print(f"  [AutoAgent] TIMEOUT — session #{session_num} killed after {max_dur}s")
            _log_knowledge(ctx, f"\nRULE: [TIMEOUT] Session #{session_num} killed after {max_dur}s. Break task smaller.\n")
        success = proc.returncode == 0
        if not success and _fallback_hints:
            try: __import__("retry").save_last_error(ctx.memory_dir, _fallback_hints)
            except Exception: pass

        # Model fallback: if Claude hit rate limits, route to best model for this task
        if not success:
            error_text = "\n".join(_fallback_hints[-10:])
            try:
                from model_fallback import is_rate_limit_error, run_fallback
                if is_rate_limit_error(error_text):
                    fb_ok, fb_model, fb_response = run_fallback(
                        boot_prompt, task_type=session_type, timeout=300,
                    )
                    if fb_ok:
                        print(fb_response, flush=True)
                        success = True
                        logger.info("Fallback to %s succeeded for %s task", fb_model, session_type)
            except Exception as fb_err:
                logger.warning("Model fallback failed: %s", fb_err)

        # Check if agent was stuck in a loop
        if frustration and frustration.is_stuck():
            fs = frustration.summary()
            print(f"  [AutoAgent] STUCK LOOP — score {fs['score']}, errors {fs['consecutive_errors']}")
            hot = ", ".join(f for f, _ in fs["hot_files"])
            _log_knowledge(ctx, f"\nRULE: [STUCK] Session #{session_num} — score {fs['score']}. Hot: {hot}. Break task smaller.\n")
            success = False

        # Council gate: periodic ship-review on work sessions. Gate on
        # session_num % 5 == 1 — under the routing cadence (get_session_type
        # sends every multiple of 5 to meta/brain/deep/audit/knowledge) that
        # residue always lands on a WORK session, so the council fires ~every
        # 5th session. The `session_type == "work"` guard keeps it correct even
        # if the cadence changes (it just fires less often, never wrongly).
        # NOTE: `% 5 == 0` was dead — those session_nums are never work.
        if success and session_type == "work" and session_num % 5 == 1:
            try:
                from council import convene_council
                diff = subprocess.run(["git", "diff", "--stat", "HEAD~1"], cwd=str(ctx.project_root),
                                      capture_output=True, text=True, timeout=10).stdout[:1000]
                if diff.strip():
                    cr = convene_council(f"Ship this change to {ctx.name}?", context=f"Diff:\n{diff}", project=ctx.name)
                    print(f"  [Council] {cr.get('confidence','?')} — {cr.get('winner','?')}")
                    if cr.get("confidence") == "LOW":
                        _log_knowledge(ctx, f"\nRULE: [COUNCIL] #{session_num} LOW confidence.\n")
                    if cr.get("decision_id"):
                        from agency_db import update_council_outcome as _upd
                        _upd(cr["decision_id"], session_success=success)
            except Exception:
                pass

        # Pre-push gate: verify tests are green after the session
        if success and session_type == "work":
            gate_ok = _pre_push_gate(ctx, session_num)
            if not gate_ok:
                print(f"  [AutoAgent] PRE-PUSH GATE FAILED — tests are red after session #{session_num}. Code NOT pushed.")
                _log_knowledge(ctx, f"\nRULE: [PRE-PUSH GATE] Session #{session_num} — BLOCKED: tests failed. Code was NOT pushed.\n")
                success = False

            # Constraint gate: check NEVER/ALWAYS/MUST rule violations
            if success:
                violations = _constraint_gate(ctx)
                if violations:
                    print(f"  [AutoAgent] CONSTRAINT GATE — {len(violations)} violation(s):")
                    for v in violations:
                        print(f"    ✗ {v['file']} violates: {v['rule']['rule']}")
                    _log_knowledge(ctx, f"\nRULE: [CONSTRAINT GATE] Session #{session_num} — BLOCKED: {len(violations)} constraint violation(s).\n")
                    success = False

        # Integrity check — verify critical files were not tampered with
        if success and integrity_baseline and session_type == "work":
            violations = check_integrity(integrity_baseline)
            if violations:
                print(f"  [AutoAgent] INTEGRITY VIOLATION — {len(violations)} file(s) modified:")
                for v in violations:
                    print(f"    ✗ {v}")
                _log_knowledge(ctx, f"\nRULE: [INTEGRITY] Session #{session_num} — ALERT: {', '.join(violations)}. Investigate.\n")

        # Save reasoning trace for meta-agent analysis
        if tracer: tracer.save(success=success)

        # Infrastructure-level session logging
        log_session_entry(ctx, session_num, session_type, success,
                          agent=agent_name or "", cost_usd=session_cost_usd,
                          model=model_for_session or "")

        # Post-session hooks: reviews, agent memory, self-improve, notify
        from post_session import run_post_session_hooks
        run_post_session_hooks(ctx, session_num, session_type, success, agent_name=agent_name or "")

        emit_event(ef, project=ctx.name, session=session_num, type="session_end", success=success, agent=agent_name)
        return success
    except KeyboardInterrupt:
        print("\n  [AutoAgent] Stopping... (current_task.md preserved)")
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except: proc.kill()
        # Bug-3 fix: write a SIGINT checkpoint stub to knowledge.md so the
        # next session can pick up where this one was killed. Pulls the last
        # ~25 tool calls from live_events.jsonl as a breadcrumb trail.
        try:
            _write_sigint_checkpoint(ctx, session_num, session_type)
        except Exception as _cp_e:
            print(f"  [AutoAgent] checkpoint write failed: {_cp_e}")
        raise
    finally:
        if locked:
            try: unlock_ctx_instruction_files(ctx)
            except Exception: pass
        # Restore the previous SIGINT handler so we don't poison the parent
        # supervisor's signal handling after this session returns.
        try:
            _signal.signal(_signal.SIGINT, _prev_sigint)
        except (ValueError, OSError, TypeError):
            pass
        # Belt-and-suspenders: if SIGINT was caught but the except path
        # above didn't fire (e.g. child died gracefully and the loop
        # returned normally before our handler raised), write the
        # checkpoint here. _write_sigint_checkpoint itself is idempotent
        # in spirit — it appends a session-specific stub each time.
        if _sigint_caught[0]:
            try:
                _write_sigint_checkpoint(ctx, session_num, session_type)
            except Exception as _cp_e:
                print(f"  [AutoAgent] checkpoint write failed (finally): {_cp_e}")
