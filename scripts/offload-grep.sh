#!/usr/bin/env bash
# Offload grep operations with summarized output
# Returns counts and limited samples instead of full matches
# Usage: offload-grep.sh '<pattern>' '<path>' [max_samples]

set -euo pipefail

PATTERN="${1:-}"
SEARCH_PATH="${2:-.}"
MAX_SAMPLES="${3:-10}"

if [[ -z "$PATTERN" ]]; then
    echo "Usage: offload-grep.sh '<pattern>' '<path>' [max_samples]"
    exit 1
fi

echo "=== Grep Summary for '$PATTERN' ==="
echo ""

# Get file matches with counts
echo "## Files with matches:"
rg -c "$PATTERN" "$SEARCH_PATH" 2>/dev/null | sort -t: -k2 -nr | head -n 20

echo ""
TOTAL_MATCHES=$(rg -c "$PATTERN" "$SEARCH_PATH" 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
TOTAL_FILES=$(rg -l "$PATTERN" "$SEARCH_PATH" 2>/dev/null | wc -l)

echo "## Statistics:"
echo "Total matches: ${TOTAL_MATCHES:-0}"
echo "Total files: ${TOTAL_FILES:-0}"
echo ""

# Show samples from top files
echo "## Sample matches (first $MAX_SAMPLES):"
rg -n "$PATTERN" "$SEARCH_PATH" 2>/dev/null | head -n "$MAX_SAMPLES"
