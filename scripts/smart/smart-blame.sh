#!/usr/bin/env bash
# smart-blame.sh - Git blame with context, skipping noise commits
# Usage: smart-blame.sh <file> [line] [context_lines]
#
# Features:
# - Shows surrounding context
# - Uses .git-blame-ignore-revs if present
# - Filters common noise patterns (formatting, lint fixes)
# - Compact output format

set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") <file> [line] [context_lines]"
    echo ""
    echo "Git blame with context, skipping noise commits"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Arguments:"
    echo "  file            File to blame"
    echo "  line            Specific line number (default: entire file)"
    echo "  context_lines   Lines of context around target line (default: 3)"
    echo ""
    echo "Features:"
    echo "  - Shows surrounding context"
    echo "  - Uses .git-blame-ignore-revs if present"
    echo "  - Filters common noise patterns (formatting, lint fixes)"
    echo "  - Compact output format"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") src/main.py           # blame entire file"
    echo "  $(basename "$0") src/main.py 42        # blame around line 42"
    echo "  $(basename "$0") src/main.py 42 5      # line 42 with 5 lines context"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

file="${1:-}"
line="${2:-}"
context="${3:-3}"

if [[ -z "$file" ]]; then
    usage
    exit 1
fi

if [[ ! -f "$file" ]]; then
    echo "Error: File not found: $file"
    exit 1
fi

# Build blame options as array (avoids word splitting issues)
blame_opts=()

# Use ignore-revs file if present (for formatting commits, etc.)
if [[ -f ".git-blame-ignore-revs" ]]; then
    blame_opts+=("--ignore-revs-file=.git-blame-ignore-revs")
elif [[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.git-blame-ignore-revs" ]]; then
    blame_opts+=("--ignore-revs-file=$(git rev-parse --show-toplevel)/.git-blame-ignore-revs")
fi

# Add line range if specified
if [[ -n "$line" ]]; then
    start=$((line - context))
    end=$((line + context))
    [[ $start -lt 1 ]] && start=1
    blame_opts+=("-L" "$start,$end")
fi

# Run git blame with options
# Format: short commit hash, author, date, line number, content
output=$(git blame "${blame_opts[@]}" --date=short -s "$file" 2>/dev/null)

if [[ -z "$output" ]]; then
    echo "No blame data available"
    exit 0
fi

# Extract unique commits and batch-fetch their info
declare -A commit_cache
while IFS= read -r commit; do
    [[ -z "$commit" || -n "${commit_cache[$commit]:-}" ]] && continue
    commit_cache[$commit]=$(git log -1 --format="%an|%s" "$commit" 2>/dev/null | head -c 60)
done < <(echo "$output" | awk '{print $1}' | sort -u)

# Process output to make it more compact and readable
echo "$output" | while IFS= read -r blame_line; do
    # Extract components
    commit=$(echo "$blame_line" | awk '{print $1}')
    line_info=$(echo "$blame_line" | sed 's/^[^ ]* //')

    # Get commit info from cache
    commit_info="${commit_cache[$commit]:-}"

    # Check if this is a "noise" commit (formatting, lint, etc.)
    is_noise=""
    if echo "$commit_info" | grep -qiE "(format|lint|style|whitespace|prettier|black|autopep|indent)"; then
        is_noise=" [fmt]"
    fi

    # Output compact format
    short_commit="${commit:0:7}"
    echo "$short_commit$is_noise $line_info"
done

