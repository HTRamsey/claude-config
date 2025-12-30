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

# Single rg pass: get all matches with context (file:line:match format)
# Cache output to avoid multiple passes
# Use -- to prevent pattern from being interpreted as option
RG_OUTPUT=$(rg -c -- "$PATTERN" "$SEARCH_PATH" 2>/dev/null || true)

if [[ -z "$RG_OUTPUT" ]]; then
    echo "No matches found"
    exit 0
fi

# Get file matches with counts (from cached output)
echo "## Files with matches:"
echo "$RG_OUTPUT" | sort -t: -k2 -nr | head -n 20

# Calculate statistics from cached output
TOTAL_MATCHES=$(echo "$RG_OUTPUT" | awk -F: '{sum+=$2} END {print sum+0}')
TOTAL_FILES=$(echo "$RG_OUTPUT" | wc -l)

echo ""
echo "## Statistics:"
echo "Total matches: ${TOTAL_MATCHES:-0}"
echo "Total files: ${TOTAL_FILES:-0}"
echo ""

# Show samples (single additional rg call for context - unavoidable)
echo "## Sample matches (first $MAX_SAMPLES):"
rg -n -- "$PATTERN" "$SEARCH_PATH" 2>/dev/null | head -n "$MAX_SAMPLES"
