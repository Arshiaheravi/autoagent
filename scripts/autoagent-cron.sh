#!/bin/bash
# AutoAgent autonomous runner — designed for cron/launchd
# Runs 1 session per project, shares knowledge, checks quality
#
# Install in crontab:
#   crontab -e
#   0 */2 * * * /path/to/autoagent/scripts/autoagent-cron.sh >> /tmp/autoagent-cron.log 2>&1
#
# Or use launchd (macOS):
#   cp scripts/com.autoagent.runner.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.autoagent.runner.plist

set -e

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PWD/engine"

echo "=== AutoAgent Autonomous Run — $(date) ==="
python3 engine/self_improve.py auto
echo "=== Done — $(date) ==="
