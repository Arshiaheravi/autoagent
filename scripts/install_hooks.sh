#!/usr/bin/env bash
# Install the repo-local git hooks.
# Run once: bash scripts/install_hooks.sh
set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
SCRIPTS_DIR="$REPO_ROOT/scripts"

chmod +x "$SCRIPTS_DIR/check_secrets.sh"

cat > "$HOOKS_DIR/pre-commit" <<'EOF'
#!/usr/bin/env bash
set -u
ROOT="$(git rev-parse --show-toplevel)"
bash "$ROOT/scripts/check_secrets.sh"
EOF

chmod +x "$HOOKS_DIR/pre-commit"
echo "Installed pre-commit hook -> $HOOKS_DIR/pre-commit"
echo "Scans for: GitHub/Anthropic/OpenAI/AWS/Telegram secrets, private-key blocks."
echo "Override (NOT recommended): git commit --no-verify"
