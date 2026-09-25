#!/usr/bin/env bash
# advisor.sh — Opus advisor consultation for Sonnet WORK sessions.
#
# Usage:
#   scripts/advisor.sh "Should I change the Pydantic model schema or add a new endpoint?"
#   scripts/advisor.sh "Review this approach" --context path/to/context.md
#
# Strips ANTHROPIC_API_KEY to bill on Max plan (not API).
# Logs every call to memory/advisor_log.md for META review.
# Caps wall-time at 120s. Single turn. Opus-4-7 only.
#
# Exit codes: 0 = response returned, 1 = empty response, 2 = bad args.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$REPO_ROOT/memory/advisor_log.md"
MAX_TURNS=1
TIMEOUT=120

if [[ $# -lt 1 ]]; then
    echo "usage: advisor.sh <question> [--context <file>]" >&2
    exit 2
fi

QUESTION="$1"; shift
CONTEXT_FILE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --context) CONTEXT_FILE="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

PROMPT="You are an Opus advisor consulted by a Sonnet executor.
Respond in <100 words. Use enumerated steps, not prose.
No preamble. Lead with the recommendation.

QUESTION:
$QUESTION"

if [[ -n "$CONTEXT_FILE" && -f "$CONTEXT_FILE" ]]; then
    PROMPT="$PROMPT

CONTEXT (from $CONTEXT_FILE):
$(head -c 8000 "$CONTEXT_FILE")"
fi

CLAUDE_BIN="$(command -v claude || echo claude)"
TIMEOUT_BIN="$(command -v gtimeout || command -v timeout || true)"

if [[ -n "$TIMEOUT_BIN" ]]; then
    RESPONSE=$(
        env -u ANTHROPIC_API_KEY "$TIMEOUT_BIN" "$TIMEOUT" \
            "$CLAUDE_BIN" -p "$PROMPT" \
            --model opus \
            --max-turns "$MAX_TURNS" \
            --output-format text \
            2>/dev/null || true
    )
else
    RESPONSE=$(
        env -u ANTHROPIC_API_KEY \
            "$CLAUDE_BIN" -p "$PROMPT" \
            --model opus \
            --max-turns "$MAX_TURNS" \
            --output-format text \
            2>/dev/null || true
    )
fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
Q_PREVIEW="${QUESTION:0:120}"
R_PREVIEW="${RESPONSE:0:160}"

mkdir -p "$(dirname "$LOG")"
{
    echo ""
    echo "## $TS"
    echo "**Q:** $Q_PREVIEW"
    echo "**A:** $R_PREVIEW"
} >> "$LOG"

if [[ -z "$RESPONSE" ]]; then
    echo "ADVISOR_EMPTY" >&2
    exit 1
fi

echo "$RESPONSE"
