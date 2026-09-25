#!/bin/bash
# Auto-commit and push active_session.md after edits
# Called by Claude Code PostToolUse hook
# Receives JSON on stdin with tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Only care about active_session.md edits
if [[ "$FILE_PATH" != *"active_session.md" ]]; then
    exit 0
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_FILE="memory/active_session.md"

cd "$REPO_DIR" || exit 0

# Only proceed if active_session.md has changes
if ! git diff --quiet "$SESSION_FILE" 2>/dev/null && [ -f "$SESSION_FILE" ]; then
    git add "$SESSION_FILE"
    git commit -m "session: auto-save active session state" -q 2>/dev/null
    git push -q 2>/dev/null &
fi

exit 0
