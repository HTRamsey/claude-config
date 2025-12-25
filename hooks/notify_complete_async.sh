#!/usr/bin/env bash
# Async notification hook - sends desktop notification for long commands
# Runs asynchronously to avoid blocking Claude
#
# PostToolUse hook for Bash tool

# Output async config FIRST - this tells Claude Code to not wait
echo '{"async":true,"asyncTimeout":10000}'

# Read context from stdin
ctx=$(cat)

# Extract tool name - only process Bash
tool_name=$(echo "$ctx" | jq -r '.tool_name // ""')
if [[ "$tool_name" != "Bash" ]]; then
    exit 0
fi

# Check duration (need > 30 seconds)
duration_ms=$(echo "$ctx" | jq -r '.duration_ms // 0')
duration_secs=$((duration_ms / 1000))

if [[ $duration_secs -lt 30 ]]; then
    exit 0
fi

# Extract command and exit code
command=$(echo "$ctx" | jq -r '.tool_input.command // ""' | head -c 50)
exit_code=$(echo "$ctx" | jq -r '.tool_result.exit_code // 0')

# Determine notification type
if [[ "$exit_code" == "0" ]]; then
    title="✓ Command Complete"
    urgency="normal"
else
    title="✗ Command Failed"
    urgency="critical"
fi

message="${command}...
Duration: ${duration_secs}s"

# Send notification (if notify-send available)
if command -v notify-send &>/dev/null; then
    notify-send \
        --urgency "$urgency" \
        --app-name "Claude Code" \
        --icon terminal \
        "$title" \
        "$message"
fi
