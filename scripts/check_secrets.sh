#!/usr/bin/env bash
# Pre-commit hook: block commits that stage likely secrets.
# Install with: scripts/install_hooks.sh  (or manually symlink to .git/hooks/pre-commit)
#
# Patterns covered:
#   GitHub PAT:          ghp_[A-Za-z0-9]{36,}
#   GitHub fine-grained: github_pat_[A-Za-z0-9_]{20,}
#   Anthropic key:       sk-ant-[A-Za-z0-9_\-]{20,}
#   OpenAI key:          sk-[A-Za-z0-9]{32,}
#   AWS access key:      AKIA[0-9A-Z]{16}
#   Telegram bot token:  [0-9]{8,}:[A-Za-z0-9_\-]{30,}
#   Generic private key: -----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----

set -u

RED=$'\033[31m'
YEL=$'\033[33m'
RST=$'\033[0m'

# Only scan files that are actually staged for commit (not working tree garbage)
STAGED=$(git diff --cached --name-only --diff-filter=ACMR)
if [ -z "$STAGED" ]; then
  exit 0
fi

# Patterns: label|regex
PATTERNS=(
  "GitHub PAT|ghp_[A-Za-z0-9]{36,}"
  "GitHub fine-grained PAT|github_pat_[A-Za-z0-9_]{20,}"
  "Anthropic key|sk-ant-[A-Za-z0-9_\\-]{20,}"
  "OpenAI key|sk-[A-Za-z0-9]{32,}"
  "AWS access key|AKIA[0-9A-Z]{16}"
  "Telegram bot token|[0-9]{8,}:[A-Za-z0-9_\\-]{30,}"
  "Private key block|-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----"
)

FAIL=0
while IFS= read -r file; do
  # Skip binary and deleted files
  [ -f "$file" ] || continue
  if file "$file" | grep -qi 'binary'; then
    continue
  fi

  for entry in "${PATTERNS[@]}"; do
    label="${entry%%|*}"
    regex="${entry#*|}"
    # -I ignores binaries, -n shows line numbers, -E extended regex
    matches=$(git diff --cached -U0 -- "$file" | grep -nE "^\+.*$regex" || true)
    if [ -n "$matches" ]; then
      printf '%s[secret-scan]%s likely %s in staged %s:\n' "$RED" "$RST" "$label" "$file" >&2
      echo "$matches" | sed 's/^/    /' >&2
      FAIL=1
    fi
  done
done <<< "$STAGED"

if [ "$FAIL" -ne 0 ]; then
  printf '\n%sCommit blocked.%s Remove the secret or override with: %sgit commit --no-verify%s (not recommended).\n' "$RED" "$RST" "$YEL" "$RST" >&2
  exit 1
fi

exit 0
