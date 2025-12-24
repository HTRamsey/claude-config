#!/usr/bin/env bash
# Offload find operations with summarized output
# Returns counts and categorized results instead of full listing
# Usage: offload-find.sh '<path>' '<pattern>' [max_results]

set -euo pipefail

SEARCH_PATH="${1:-.}"
PATTERN="${2:-*}"
MAX_RESULTS="${3:-30}"

echo "=== Find Summary for '$PATTERN' in '$SEARCH_PATH' ==="
echo ""

# Find files matching pattern
MATCHES=$(find "$SEARCH_PATH" -name "$PATTERN" -type f 2>/dev/null)
TOTAL=$(echo "$MATCHES" | grep -c . || echo 0)

echo "## Statistics:"
echo "Total matches: $TOTAL"
echo ""

# Group by directory
echo "## By directory (top 10):"
echo "$MATCHES" | xargs -I{} dirname {} 2>/dev/null | sort | uniq -c | sort -rn | head -n 10
echo ""

# Group by extension
echo "## By extension:"
echo "$MATCHES" | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -n 10
echo ""

# Recent files
echo "## Most recent (top $MAX_RESULTS):"
echo "$MATCHES" | head -n "$MAX_RESULTS"
