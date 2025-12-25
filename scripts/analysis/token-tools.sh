#!/usr/bin/env bash
set -euo pipefail
# Token optimization tools - source this file to get helper functions
# Usage: source ~/.claude/scripts/token-tools.sh

CLAUDE_SCRIPTS="${HOME}/.claude/scripts"

# Quick cost check alias
alias ccost='echo "Run /cost in Claude Code to see session costs"'

# Compress JSON - extract specific fields
# Usage: cjson '<json>' 'field1,field2'
cjson() {
    "$CLAUDE_SCRIPTS/compress-json.sh" "$1" "$2"
}

# Compress logs - extract errors/warnings
# Usage: clogs '<logs>' [max_lines]
clogs() {
    "$CLAUDE_SCRIPTS/compress-logs.sh" "$1" "${2:-50}"
}

# Compress list - filter and limit
# Usage: clist '<list>' '<filter>' [limit]
clist() {
    "$CLAUDE_SCRIPTS/compress-list.sh" "$1" "${2:-.*}" "${3:-20}"
}

# Offload grep with summary
# Usage: ogrep '<pattern>' [path] [max_samples]
ogrep() {
    "$CLAUDE_SCRIPTS/offload-grep.sh" "$1" "${2:-.}" "${3:-10}"
}

# Offload find with summary
# Usage: ofind [path] '<pattern>' [max_results]
ofind() {
    "$CLAUDE_SCRIPTS/offload-find.sh" "${1:-.}" "${2:-*}" "${3:-30}"
}

# Offload API call with compression
# Usage: oapi '<curl_command>' 'field1,field2'
oapi() {
    "$CLAUDE_SCRIPTS/offload-api.sh" "$1" "$2"
}

# Token budget check
token_budget() {
    local tokens="${1:-0}"
    local budget=50000

    if [[ $tokens -gt $budget ]]; then
        echo "WARNING: $tokens tokens exceeds budget of $budget"
        echo "Consider running /compact or /optimize-context"
        return 1
    else
        echo "OK: $tokens tokens ($(( tokens * 100 / budget ))% of budget)"
        return 0
    fi
}

# Show available commands
token_help() {
    echo "Token Optimization Tools"
    echo "========================"
    echo ""
    echo "Compression:"
    echo "  cjson '<json>' 'fields'     - Extract fields from JSON"
    echo "  clogs '<logs>' [max]        - Summarize logs (errors/warnings)"
    echo "  clist '<list>' 'filter' [n] - Filter and limit lists"
    echo ""
    echo "Offloading:"
    echo "  ogrep 'pattern' [path]      - Grep with summary output"
    echo "  ofind [path] 'pattern'      - Find with categorized summary"
    echo "  oapi 'curl cmd' 'fields'    - API call with compression"
    echo ""
    echo "Monitoring:"
    echo "  token_budget <count>        - Check against 50K budget"
    echo "  ~/.claude/scripts/monitor-tokens.sh"
    echo ""
}

echo "Token tools loaded. Run 'token_help' for commands."
