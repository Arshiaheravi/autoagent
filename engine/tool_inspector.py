#!/usr/bin/env python3
"""Tool Inspector — pre-execution safety checks on Claude CLI tool calls.

Inspired by Goose's multi-inspector pipeline. Checks BEFORE execution,
not after. Catches dangerous operations that prompt injection could trigger.

Inspectors:
  1. Path inspector — blocks writes to sensitive directories
  2. Command inspector — blocks dangerous shell commands
  3. Egress inspector — flags network calls to unknown domains
  4. Secrets inspector — prevents leaking env vars or credentials

Wired into Claude Code hooks (PreToolUse) so checks run before
every tool call, not just post-session.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class InspectorResult:
    """Result of a tool inspection."""
    allowed: bool
    reason: str = ""
    inspector: str = ""
    severity: str = "info"  # info, warning, block


# ── Sensitive paths that should never be written to ──────────────────────────

_BLOCKED_PATHS = re.compile(
    r'(?:^|/)('
    r'\.ssh|\.aws|\.gnupg|\.kube|\.docker|\.config/gh|'
    r'\.npmrc|\.pypirc|\.netrc|\.env(?!\.example)|'
    r'etc/passwd|etc/shadow|etc/hosts|'
    r'\.git/config|\.git/hooks|'
    r'node_modules/.package-lock|'
    r'__pycache__'
    r')(?:/|$)',
    re.IGNORECASE,
)

_SENSITIVE_EXTENSIONS = {'.pem', '.key', '.p12', '.pfx', '.keystore', '.jks'}


# ── Dangerous commands ───────────────────────────────────────────────────────

_BLOCKED_COMMANDS = [
    re.compile(r'\brm\s+(-rf?|--recursive)\s+[/~]', re.IGNORECASE),
    re.compile(r'\brm\s+-rf?\s+\.\s*$'),
    re.compile(r'\bchmod\s+777\b'),
    re.compile(r'\bcurl\b.*\|\s*(ba)?sh\b'),
    re.compile(r'\bwget\b.*\|\s*(ba)?sh\b'),
    re.compile(r'\beval\b.*\$\('),
    re.compile(r'\bnc\s+-[el]'),  # netcat listeners
    re.compile(r'\bpython[3]?\s+-c\b.*\b(exec|eval|__import__)\b'),
    re.compile(r'\bpkill\b.*-9'),
    re.compile(r'\bkillall\b'),
    re.compile(r'\bdd\s+if=.*of=/dev/'),
    re.compile(r'\bmkfs\b'),
    re.compile(r'\bsudo\b'),
    re.compile(r'\bsu\s+-?\s*$'),
    re.compile(r'>\s*/dev/sd[a-z]'),
    re.compile(r'\biptables\b'),
    re.compile(r'\bsystemctl\s+(stop|disable|mask)\b'),
]

# Commands that exfiltrate data
_EXFIL_COMMANDS = [
    re.compile(r'\bcurl\b.*(-d|--data|--upload-file)\b'),
    re.compile(r'\bwget\s+--post-(data|file)\b'),
    re.compile(r'\bscp\b.*@'),
    re.compile(r'\brsync\b.*@'),
    re.compile(r'\bgit\s+push\b.*(?!origin\b)'),  # push to non-origin
]

# ── Secrets patterns ─────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r'\bprintenv\b'),
    re.compile(r'\benv\b\s*$'),
    re.compile(r'\becho\s+\$[A-Z_]*(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL)', re.IGNORECASE),
    re.compile(r'cat\s+.*\.(env|pem|key|credentials)', re.IGNORECASE),
    re.compile(r'\$TELEGRAM_BOT_TOKEN|\$ANTHROPIC_API_KEY|\$JWT_SECRET', re.IGNORECASE),
]


# ── Inspectors ───────────────────────────────────────────────────────────────

def inspect_path(file_path: str) -> InspectorResult:
    """Check if a file path is safe to read/write."""
    if not file_path:
        return InspectorResult(allowed=True)

    # Block sensitive directories
    if _BLOCKED_PATHS.search(file_path):
        return InspectorResult(
            allowed=False,
            reason=f"Blocked: write to sensitive path {file_path}",
            inspector="path",
            severity="block",
        )

    # Block sensitive file extensions
    for ext in _SENSITIVE_EXTENSIONS:
        if file_path.lower().endswith(ext):
            return InspectorResult(
                allowed=False,
                reason=f"Blocked: sensitive file type {ext}",
                inspector="path",
                severity="block",
            )

    return InspectorResult(allowed=True)


def inspect_command(command: str) -> InspectorResult:
    """Check if a shell command is safe to execute."""
    if not command:
        return InspectorResult(allowed=True)

    # Block destructive commands
    for pattern in _BLOCKED_COMMANDS:
        if pattern.search(command):
            return InspectorResult(
                allowed=False,
                reason=f"Blocked: dangerous command pattern",
                inspector="command",
                severity="block",
            )

    # Block secret access. MUST run before the exfil warning below: a command
    # that both touches a secret and exfiltrates (e.g. `cat .env | curl ...`)
    # would otherwise hit the warning early-return and be downgraded from BLOCK
    # to allowed-with-warning. Block-severity checks always precede warnings.
    for pattern in _SECRET_PATTERNS:
        if pattern.search(command):
            return InspectorResult(
                allowed=False,
                reason=f"Blocked: attempt to access secrets/credentials",
                inspector="secrets",
                severity="block",
            )

    # Flag exfiltration attempts (warning, not block — could be legitimate)
    for pattern in _EXFIL_COMMANDS:
        if pattern.search(command):
            return InspectorResult(
                allowed=True,
                reason=f"Warning: potential data exfiltration",
                inspector="egress",
                severity="warning",
            )

    return InspectorResult(allowed=True)


def inspect_tool_call(tool_name: str, tool_input: dict) -> InspectorResult:
    """Main entry point — inspect any tool call before execution.

    Routes to the appropriate inspector based on tool type.
    """
    if tool_name in ("Write", "Edit"):
        path = tool_input.get("file_path", "")
        result = inspect_path(path)
        if not result.allowed:
            logger.warning("[INSPECTOR] %s on %s: %s", tool_name, path, result.reason)
            return result

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        result = inspect_command(cmd)
        if not result.allowed or result.severity == "warning":
            logger.warning("[INSPECTOR] Bash: %s — %s", result.reason, cmd[:100])
            return result

    if tool_name == "Read":
        path = tool_input.get("file_path", "")
        # Allow reads but flag sensitive paths
        if _BLOCKED_PATHS.search(path or ""):
            return InspectorResult(
                allowed=True,
                reason=f"Warning: reading sensitive path {path}",
                inspector="path",
                severity="warning",
            )

    return InspectorResult(allowed=True)


# ── Hooks integration ────────────────────────────────────────────────────────

def generate_inspector_hooks() -> dict:
    """Generate Claude Code hooks config that runs the inspector.

    Returns a hooks config dict that can be merged into .claude/settings.json.
    The hook runs a Python one-liner that calls inspect_tool_call() and
    exits non-zero if the call should be blocked.
    """
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|Write|Edit",
                    "command": (
                        'python3 -c "'
                        "import sys,json; sys.path.insert(0,'.autoagent/engine' if __import__('os').path.exists('.autoagent/engine') else 'engine');"
                        "from tool_inspector import inspect_tool_call;"
                        "d=json.loads(sys.stdin.read());"
                        "r=inspect_tool_call(d.get('tool_name',''),d.get('tool_input',{}));"
                        "sys.exit(1) if not r.allowed else None"
                        '"'
                    ),
                }
            ]
        }
    }
