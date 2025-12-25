#!/usr/bin/env bash
set -euo pipefail
# Token optimization tools - source this file to get helper functions
# Usage: source ~/.claude/scripts/analysis/token-tools.sh

CLAUDE_SCRIPTS="${HOME}/.claude/scripts"

# Quick cost check alias
alias ccost='echo "Run /cost in Claude Code to see session costs"'

# Compress JSON - extract specific fields
# Usage: cjson '<json>' 'field1,field2'
cjson() {
    "$CLAUDE_SCRIPTS/compress/compress.sh" --type json "$1" "$2"
}

# Compress logs - extract errors/warnings
# Usage: clogs '<logs>' [max_lines]
clogs() {
    "$CLAUDE_SCRIPTS/compress/compress.sh" --type logs "$1" "${2:-50}"
}

# Compress list - filter and limit
# Usage: clist '<list>' '<filter>' [limit]
clist() {
    "$CLAUDE_SCRIPTS/compress/compress.sh" --type list "$1" "${2:-.*}" "${3:-20}"
}

# Offload grep with summary
# Usage: ogrep '<pattern>' [path] [max_samples]
ogrep() {
    "$CLAUDE_SCRIPTS/search/offload-grep.sh" "$1" "${2:-.}" "${3:-10}"
}

# Offload find with summary
# Usage: ofind [path] '<pattern>' [max_results]
ofind() {
    "$CLAUDE_SCRIPTS/search/offload-find.sh" "${1:-.}" "${2:-*}" "${3:-30}"
}

# Token budget check
token_budget() {
    local tokens="${1:-0}"
    local budget=50000
    if [[ $tokens -gt $budget ]]; then
        echo "WARNING: $tokens tokens exceeds budget of $budget"
        return 1
    else
        echo "OK: $tokens tokens ($(( tokens * 100 / budget ))% of budget)"
        return 0
    fi
}

# Show available commands
token_help() {
    cat << 'HELP'
Token Optimization Tools
========================

Compression:
  cjson '<json>' 'fields'     - Extract fields from JSON
  clogs '<logs>' [max]        - Summarize logs (errors/warnings)
  clist '<list>' 'filter' [n] - Filter and limit lists

Offloading:
  ogrep 'pattern' [path]      - Grep with summary output
  ofind [path] 'pattern'      - Find with categorized summary

Monitoring:
  token_budget <count>        - Check against 50K budget
HELP
}

echo "Token tools loaded. Run 'token_help' for commands."
