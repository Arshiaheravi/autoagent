#!/usr/bin/env bash
# council.sh — 5-model council debate for high-stakes decisions.
#
# Use when: advisor can't resolve, strategic/architectural choice,
# billing/auth/data-write design fork, or disagreement between sources.
#
# Usage:
#   scripts/council.sh --question "Should X use Y or Z?" --task <TASK_ID>
#   scripts/council.sh --question "..." --task <ID> --context path/to/file.md
#
# Behavior:
#   - Runs convene_council_with_debate (3 rounds max)
#   - HIGH confidence → returns synthesis on stdout
#   - No convergence → benches task to memory/benched/<ts>_<task>.md
#     and returns BENCHED:<path> on stdout so the executor can skip+log
#
# Cost: one council round ≈ 7-10k tokens across 5 backends.
# Spends Max plan + API keys; only call for decisions where mistake cost >> call cost.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

QUESTION=""
TASK_ID=""
CONTEXT_FILE=""
MAX_ROUNDS=3

while [[ $# -gt 0 ]]; do
    case "$1" in
        --question) QUESTION="$2"; shift 2 ;;
        --task)     TASK_ID="$2"; shift 2 ;;
        --context)  CONTEXT_FILE="$2"; shift 2 ;;
        --rounds)   MAX_ROUNDS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "$QUESTION" || -z "$TASK_ID" ]]; then
    echo "usage: council.sh --question <q> --task <id> [--context <file>] [--rounds N]" >&2
    exit 2
fi

CONTEXT=""
if [[ -n "$CONTEXT_FILE" && -f "$CONTEXT_FILE" ]]; then
    CONTEXT=$(head -c 8000 "$CONTEXT_FILE")
fi

cd "$REPO_ROOT"
python3 - <<PYEOF
import json, os, sys
sys.path.insert(0, "$REPO_ROOT/engine")
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from council import convene_council_with_debate

result = convene_council_with_debate(
    question=${QUESTION@Q},
    context=${CONTEXT@Q},
    max_rounds=${MAX_ROUNDS},
    task_id=${TASK_ID@Q},
)

status = result.get("status", "unknown")
if status == "converged":
    print(result.get("synthesis", "").strip())
    sys.exit(0)
elif status == "benched":
    print(f"BENCHED:{result['bench_path']}")
    sys.exit(3)
else:
    print(f"ERROR: council returned unexpected status {status}", file=sys.stderr)
    sys.exit(1)
PYEOF
