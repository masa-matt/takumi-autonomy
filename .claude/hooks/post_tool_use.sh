#!/usr/bin/env bash
# post_tool_use.sh
# Runs after every tool execution in Claude Code sessions.
# Appends an audit log entry; always exits 0.

set -euo pipefail

LOG_DIR="runtime/logs/claude_code"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/post_tool_use.jsonl"

INPUT=$(cat)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")
SUCCESS=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(not bool(d.get('error',''))).lower())" 2>/dev/null || echo "unknown")

echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"post_tool_use\",\"tool\":\"$TOOL_NAME\",\"success\":$SUCCESS}" >> "$LOG_FILE"

exit 0
