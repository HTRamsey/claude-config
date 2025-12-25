#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat << 'EOF'
Usage: claude-safe.sh "prompt"
       claude-safe.sh -f prompt.txt
       echo "prompt" | claude-safe.sh -

Run Claude Code with automation safeguards.
Prevents runaway token consumption in automated/CI workflows.

Environment Variables:
  MAX_TURNS=25          Maximum conversation turns (default: 25)
  TIMEOUT_MINUTES=10    Total time limit (default: 10)
  MAX_TOKENS=100000     Approximate token budget (default: 100000)
  DRY_RUN=0|1           Preview without running (default: 0)
  OUTPUT_FORMAT=text    Output format: text or json (default: text)

Options:
  -h, --help    Show this help

Examples:
  claude-safe.sh "Fix the tests"
  claude-safe.sh -f task.txt
  echo "Refactor auth module" | claude-safe.sh -
  MAX_TURNS=50 TIMEOUT_MINUTES=20 claude-safe.sh "Complex task"
EOF
    exit 0
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

# Load common utilities
source "$(dirname "$0")/../lib/common.sh"

# Defaults (can be overridden via environment)
MAX_TURNS="${MAX_TURNS:-25}"
TIMEOUT_MINUTES="${TIMEOUT_MINUTES:-10}"
MAX_TOKENS="${MAX_TOKENS:-100000}"
DRY_RUN="${DRY_RUN:-0}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}"  # text or json

# Parse arguments
PROMPT=""
if [[ "$1" == "-f" ]]; then
    # Read from file
    if [[ -f "$2" ]]; then
        PROMPT=$(cat "$2")
    else
        log_error "File not found: $2"
        exit 1
    fi
elif [[ "$1" == "-" ]]; then
    # Read from stdin
    PROMPT=$(cat)
elif [[ -n "$1" ]]; then
    PROMPT="$1"
else
    echo "Usage: claude-safe.sh \"prompt\" | -f file.txt | -"
    echo ""
    echo "Environment variables:"
    echo "  MAX_TURNS=$MAX_TURNS          Max conversation turns"
    echo "  TIMEOUT_MINUTES=$TIMEOUT_MINUTES      Total time limit"
    echo "  MAX_TOKENS=$MAX_TOKENS        Approximate token budget"
    echo "  DRY_RUN=0|1            Preview without running"
    echo "  OUTPUT_FORMAT=text|json Output format"
    exit 1
fi

# Calculate timeout in seconds
TIMEOUT_SECONDS=$((TIMEOUT_MINUTES * 60))

log_info "Automation Safeguards Active:"
log_info "  Max turns: $MAX_TURNS"
log_info "  Timeout: ${TIMEOUT_MINUTES}m (${TIMEOUT_SECONDS}s)"
log_info "  Token budget: ~$MAX_TOKENS"

if [[ "$DRY_RUN" == "1" ]]; then
    log_warn "DRY RUN - would execute:"
    echo "claude --max-turns $MAX_TURNS --output-format $OUTPUT_FORMAT -p \"$PROMPT\""
    exit 0
fi

# Build claude command with safeguards
CLAUDE_CMD=(
    "claude"
    "--max-turns" "$MAX_TURNS"
    "--output-format" "$OUTPUT_FORMAT"
    "-p" "$PROMPT"
)

# Run with timeout
log_info "Starting Claude with safeguards..."
START_TIME=$(date +%s)

timeout "$TIMEOUT_SECONDS" "${CLAUDE_CMD[@]}"
EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [[ $EXIT_CODE -eq 124 ]]; then
    log_error "Claude timed out after ${TIMEOUT_MINUTES} minutes"
    exit 124
elif [[ $EXIT_CODE -ne 0 ]]; then
    log_error "Claude exited with code $EXIT_CODE"
    exit $EXIT_CODE
fi

log_info "Completed in ${DURATION}s"
