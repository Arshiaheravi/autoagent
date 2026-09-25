#!/usr/bin/env bash
# knowledge.sh — CLI wrapper for engine/knowledge_db.py.
#
# Usage:
#   scripts/knowledge.sh search "pydantic"          # top 5 matches
#   scripts/knowledge.sh search "pydantic" 10        # top 10 matches
#   scripts/knowledge.sh recent                      # 10 most recent rules
#   scripts/knowledge.sh add "Always grep ORM cols before seed"
#   scripts/knowledge.sh rebuild                     # reindex from knowledge.md
#   scripts/knowledge.sh count                       # rule count
#
# DB lives at memory/knowledge.db (gitignored, FTS5 index).
# Markdown at memory/knowledge.md remains the source of truth.
# Agent sessions should call `search <query>` to find relevant prior rules
# without reading the full markdown tail.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
    echo "usage: knowledge.sh {search|recent|add|rebuild|count} [args...]" >&2
    exit 2
fi
shift

case "$cmd" in
    search)
        q="${1:-}"
        limit="${2:-5}"
        if [[ -z "$q" ]]; then
            echo "search needs a query" >&2; exit 2
        fi
        "$PY" "$REPO_ROOT/engine/knowledge_db.py" search "$q" --limit "$limit"
        ;;
    recent)
        limit="${1:-10}"
        "$PY" "$REPO_ROOT/engine/knowledge_db.py" recent --limit "$limit"
        ;;
    add)
        rule="${1:-}"
        source="${2:-manual}"
        if [[ -z "$rule" ]]; then
            echo "add needs a rule text" >&2; exit 2
        fi
        "$PY" "$REPO_ROOT/engine/knowledge_db.py" add "$rule" --source "$source"
        ;;
    rebuild|count)
        "$PY" "$REPO_ROOT/engine/knowledge_db.py" "$cmd"
        ;;
    *)
        echo "unknown command: $cmd" >&2
        echo "usage: knowledge.sh {search|recent|add|rebuild|count}" >&2
        exit 2
        ;;
esac
