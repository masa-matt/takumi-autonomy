#!/usr/bin/env bash
# session_stop.sh
# Runs when the Claude Code agent loop stops.
# Reminds about handoff discipline and logs session end.

set -euo pipefail

LOG_DIR="runtime/logs/claude_code"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sessions.jsonl"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"session_stop\"}" >> "$LOG_FILE"

# Print handoff reminder to stderr (visible in Claude Code output)
cat >&2 <<'EOF'
─────────────────────────────────────────────────
[Takumi Autonomy] Session ending.
Handoff checklist (CLAUDE.md §Always leave a handoff trail):
  □ docs/handoff.md updated?
  □ Memory saved (--skill if applicable)?
  □ Checkpoint status current?
─────────────────────────────────────────────────
EOF

exit 0
