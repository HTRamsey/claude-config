#!/usr/bin/env bash
# batch-select.sh - Non-interactive batch selection using fzf
# Usage: batch-select.sh <input-command> <filter-pattern> [limit]
# Filters input without interactive mode for Claude compatibility

set -e

input_cmd="$1"
filter="$2"
limit="${3:-20}"

if [[ -z "$input_cmd" ]]; then
    echo "Usage: batch-select.sh <input-command> <filter-pattern> [limit]"
    echo "Example: batch-select.sh 'find . -name \"*.py\"' 'test' 10"
    exit 1
fi

# Security: Only allow safe file-listing commands
if ! [[ "$input_cmd" =~ ^(find|fd|ls|git\ ls-files|rg\ --files)[[:space:]] ]]; then
    echo "Error: Only find, fd, ls, git ls-files, or rg --files commands allowed" >&2
    exit 1
fi

# Block dangerous patterns
if [[ "$input_cmd" =~ [\;\|\&\`] ]] || [[ "$input_cmd" =~ \$\( ]] || [[ "$input_cmd" =~ -exec ]]; then
    echo "Error: Command contains prohibited patterns" >&2
    exit 1
fi

if command -v fzf &>/dev/null; then
    # Use fzf in filter mode (non-interactive)
    bash -c "$input_cmd" 2>/dev/null | fzf --filter="$filter" 2>/dev/null | head -"$limit"
else
    # Fallback to grep
    bash -c "$input_cmd" 2>/dev/null | grep -i "$filter" 2>/dev/null | head -"$limit"
fi
