#!/usr/bin/env bash
# pre_tool_use.sh
# Runs before every tool execution in Claude Code sessions.
# Receives tool event JSON on stdin; exits 0 to allow, 2 to block.

set -euo pipefail

LOG_DIR="runtime/logs/claude_code"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pre_tool_use.jsonl"

# Read the event from stdin
INPUT=$(cat)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")

# Append audit log entry
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"pre_tool_use\",\"tool\":\"$TOOL_NAME\"}" >> "$LOG_FILE"

# Block unconditionally dangerous shell patterns
if echo "$INPUT" | grep -qE '"(rm -rf|dd if=|mkfs|chmod 777|curl.*\|.*bash|wget.*\|.*bash)"'; then
  echo "BLOCKED by pre_tool_use hook: dangerous pattern detected" >&2
  exit 2
fi

exit 0
