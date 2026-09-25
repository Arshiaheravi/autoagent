#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session hooks — Claude Code hooks config generation and writing.

Extracted from session_analytics.py to keep each module under 300 lines.
"""
import json
import re
from pathlib import Path

from registry import ProjectContext


# ── PreCompact context preservation ──────────────────────────


def build_precompact_summary(current_task_path: Path) -> str:
    """Build a CONTEXT_SUMMARY block from current_task.md.

    Returns empty string if no active task or file missing.
    Pure function: Path → str, no side effects.
    """
    if not current_task_path.exists():
        return ""
    text = current_task_path.read_text(encoding="utf-8")
    if "no current task" in text.lower():
        return ""
    # Extract task name from "# Current Task: <name>"
    m = re.search(r"#\s*Current Task:\s*(.+)", text)
    task_name = m.group(1).strip() if m else "unknown"
    # Parse checked/unchecked steps
    done = re.findall(r"- \[x\]\s*(.+)", text)
    pending = re.findall(r"- \[ \]\s*(.+)", text)
    next_step = pending[0].strip() if pending else "none"
    lines = [
        "CONTEXT_SUMMARY:",
        f"- Task: {task_name}",
        f"- Completed: {len(done)} steps done",
        f"- Remaining: {len(pending)} steps",
        f"- Next step: {next_step}",
    ]
    return "\n".join(lines)


def write_precompact_summary(current_task_path: Path) -> bool:
    """Append CONTEXT_SUMMARY to current_task.md before compaction.

    Returns True if summary was written, False if skipped.
    """
    summary = build_precompact_summary(current_task_path)
    if not summary:
        return False
    existing = current_task_path.read_text(encoding="utf-8")
    current_task_path.write_text(
        existing.rstrip() + "\n\n" + summary + "\n", encoding="utf-8"
    )
    return True


# ── Interactive Planning — pure functions ─────────────────────


def format_plan_message(plan_text: str) -> str:
    """Format current_task.md content into a Telegram-friendly numbered plan.

    Returns empty string if no active task.
    Pure function: str → str.
    """
    if not plan_text.strip() or "no current task" in plan_text.lower():
        return ""
    m = re.search(r"#\s*Current Task:\s*(.+)", plan_text)
    task_name = m.group(1).strip() if m else "Unknown task"
    done = re.findall(r"- \[x\]\s*(.+)", plan_text)
    pending = re.findall(r"- \[ \]\s*(.+)", plan_text)
    lines = [f"📋 <b>{task_name}</b>\n"]
    step_num = 1
    for s in done:
        lines.append(f"  ✅ {step_num}. {s.strip()}")
        step_num += 1
    for s in pending:
        lines.append(f"  ⬜ {step_num}. {s.strip()}")
        step_num += 1
    lines.append(f"\n<i>{len(done)} done, {len(pending)} remaining</i>")
    lines.append("<i>Reply: 'ok' to approve, 'remove N', 'add: text', 'move N to M', or send a full replacement list.</i>")
    return "\n".join(lines)


def parse_plan_edit(plan_text: str, edit_reply: str) -> str:
    """Apply an edit command to a plan and return updated plan text.

    Supported edits:
      - 'ok' / 'approve' / 'lgtm' → no change
      - 'remove N' → remove step N
      - 'add: description' → append new step
      - 'move N to M' → reorder step N to position M
      - Lines starting with '- [ ]' → full replacement of all steps
    Pure function: (str, str) → str.
    """
    reply = edit_reply.strip()
    # Approval — no change
    if reply.lower() in ("ok", "approve", "lgtm", "looks good", "yes", "y"):
        return plan_text

    # Extract header (everything before first step) and steps
    all_steps = re.findall(r"- \[[ x]\]\s*(.+)", plan_text)
    checked = [bool(m) for m in re.finditer(r"- \[x\]", plan_text)]
    # Pad checked if mismatch
    while len(checked) < len(all_steps):
        checked.append(False)

    # Full replacement — reply contains markdown checklist items
    if "- [ ]" in reply:
        new_steps = re.findall(r"- \[ \]\s*(.+)", reply)
        if new_steps:
            return _rebuild_plan(plan_text, new_steps, [False] * len(new_steps))

    # Remove step N
    m_remove = re.match(r"remove\s+(\d+)", reply, re.IGNORECASE)
    if m_remove:
        idx = int(m_remove.group(1)) - 1  # 1-indexed to 0-indexed
        if 0 <= idx < len(all_steps):
            all_steps.pop(idx)
            checked.pop(idx)
            return _rebuild_plan(plan_text, all_steps, checked)
        return plan_text

    # Add step
    m_add = re.match(r"add:\s*(.+)", reply, re.IGNORECASE)
    if m_add:
        all_steps.append(m_add.group(1).strip())
        checked.append(False)
        return _rebuild_plan(plan_text, all_steps, checked)

    # Move N to M
    m_move = re.match(r"move\s+(\d+)\s+to\s+(\d+)", reply, re.IGNORECASE)
    if m_move:
        src = int(m_move.group(1)) - 1
        dst = int(m_move.group(2)) - 1
        if 0 <= src < len(all_steps) and 0 <= dst < len(all_steps):
            step = all_steps.pop(src)
            chk = checked.pop(src)
            all_steps.insert(dst, step)
            checked.insert(dst, chk)
            return _rebuild_plan(plan_text, all_steps, checked)
        return plan_text

    return plan_text


def _rebuild_plan(original: str, steps: list, checked: list) -> str:
    """Rebuild plan text with updated steps, preserving header."""
    m = re.search(r"#\s*Current Task:\s*(.+)", original)
    task_name = m.group(1).strip() if m else "Unknown task"
    pending = sum(1 for c in checked if not c)
    total = len(steps)
    lines = [
        f"# Current Task: {task_name}",
        f"Steps: {total} total | {pending} remaining",
    ]
    for step, done in zip(steps, checked):
        mark = "x" if done else " "
        lines.append(f"- [{mark}] {step}")
    return "\n".join(lines) + "\n"


def generate_hooks_config(ctx: ProjectContext) -> dict:
    """Generate Claude Code hooks configuration for automated quality enforcement.

    Returns a dict suitable for writing to .claude/settings.local.json.
    Hooks:
      - PreToolUse (Write|Edit): Block edits to .gitignored paths
      - PreToolUse (Bash): Block dangerous commands (rm -rf, force push, drop table)
      - PostToolUse (Write|Edit): Python syntax check on .py files
      - PostToolUse (Write|Edit): Auto-run relevant pytest after .py file edits
    """
    gitignore_check = (
        "python3 -c \""
        "import sys, json, subprocess; "
        "d = json.load(sys.stdin); "
        "p = d.get('tool_input', {}).get('file_path', ''); "
        "r = subprocess.run(['git', 'check-ignore', '-q', p], capture_output=True) "
        "if p else None; "
        "sys.exit(1) if r and r.returncode == 0 else sys.exit(0)"
        "\""
    )
    # Full inspector pipeline — checks paths, commands, secrets, egress.
    # exit(2) is REQUIRED to actually block a PreToolUse call in Claude Code;
    # any other non-zero exit is non-blocking (the tool would still run). This is
    # the security guard (dangerous commands / secret access / exfil), so a
    # disallowed call must hard-block. (gitignore_check above stays exit(1) on
    # purpose — hard-blocking every gitignored write would brick memory/config.)
    inspector_check = (
        "python3 -c \""
        "import sys,json,os; sys.path.insert(0,os.environ.get('PYTHONPATH','engine'));"
        "from tool_inspector import inspect_tool_call;"
        "d=json.load(sys.stdin);"
        "r=inspect_tool_call(d.get('tool_name',''),d.get('tool_input',{}));"
        "(sys.stderr.write((getattr(r,'reason','') or 'blocked by inspector')+chr(10)), sys.exit(2)) if not r.allowed else None"
        "\""
    )
    syntax_check = (
        "python3 -c \""
        "import sys, json, py_compile; "
        "d = json.load(sys.stdin); "
        "p = d.get('tool_input', {}).get('file_path', ''); "
        "py_compile.compile(p, doraise=True) if p.endswith('.py') else None"
        "\""
    )
    auto_test = (
        "python3 -c \""
        "import sys, json, subprocess, os; "
        "d = json.load(sys.stdin); "
        "p = d.get('tool_input', {}).get('file_path', ''); "
        "exit() if not p.endswith('.py') else None; "
        "d2 = os.path.dirname(p); bn = os.path.basename(p); "
        "tf = os.path.join(d2, 'test_' + bn) if not bn.startswith('test_') else p; "
        "subprocess.run(['python3', '-m', 'pytest', tf, '-x', '-q'], "
        "capture_output=True) if os.path.exists(tf) else None"
        "\""
    )

    # PreCompact: preserve context summary in current_task.md
    memory_dir = ctx.project_root / ".autoagent" / "memory"
    precompact_cmd = (
        "python3 -c \""
        "import sys,os; sys.path.insert(0,os.path.join("
        f"'{ctx.project_root}','engine'));"
        "from session_hooks import write_precompact_summary;"
        "from pathlib import Path;"
        f"write_precompact_summary(Path('{memory_dir}/current_task.md'))"
        "\""
    )

    return {
        "hooks": {
            "PreCompact": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": precompact_cmd},
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {"type": "command", "command": gitignore_check},
                        {"type": "command", "command": inspector_check},
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": inspector_check},
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {"type": "command", "command": syntax_check},
                        {"type": "command", "command": auto_test,
                         "async": True},
                    ],
                }
            ],
        }
    }


def generate_hooks_settings_json(ctx: ProjectContext) -> str:
    """Serialize the hooks config for inline delivery via `claude --settings`.

    Preferred over write_hooks_config in the session spawn path: the CLI loads
    these hooks directly from the argv string, so they apply even when the
    project root is read-only (sandboxed / worktree contexts) — no file write,
    no project-tree pollution. See run.py claude_args.
    """
    return json.dumps(generate_hooks_config(ctx))


def write_hooks_config(ctx: ProjectContext):
    """Write hooks config to .claude/settings.local.json in the project root.

    Best-effort: in sandboxed or worktree contexts the project root may be
    read-only. Hooks are optional (the pre-push + constraint gates in run.py
    enforce regardless), so a write failure must NOT crash the session.
    """
    config = generate_hooks_config(ctx)
    claude_dir = ctx.project_root / ".claude"
    settings_file = claude_dir / "settings.local.json"
    try:
        claude_dir.mkdir(exist_ok=True)
        existing = {}
        if settings_file.exists():
            try:
                existing = json.loads(settings_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing["hooks"] = config["hooks"]
        settings_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"  [AutoAgent] hooks config not installed ({settings_file}): {e}. "
              f"Continuing — pre-push/constraint gates run regardless.")
