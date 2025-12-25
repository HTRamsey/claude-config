#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat << 'EOF'
Usage: batch-select.sh <input-command> <filter-pattern> [limit]

Non-interactive batch selection using fzf.
Filters input without interactive mode for Claude compatibility.

Options:
  -h, --help    Show this help

Examples:
  batch-select.sh 'find . -name "*.py"' 'test' 10
  batch-select.sh 'fd -e ts' 'component' 20
  batch-select.sh 'git ls-files' 'src' 15
EOF
    exit 0
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

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

# Safe command execution using arrays instead of bash -c
# Parse the command into an array for safe execution
# shellcheck disable=SC2206
cmd_array=($input_cmd)

# Execute the command safely
output=""
if ! output=$("${cmd_array[@]}" 2>/dev/null); then
    echo "Error: Command execution failed" >&2
    exit 1
fi

if command -v fzf &>/dev/null; then
    # Use fzf in filter mode (non-interactive)
    echo "$output" | fzf --filter="$filter" 2>/dev/null | head -"$limit"
else
    # Fallback to grep
    echo "$output" | grep -i "$filter" 2>/dev/null | head -"$limit"
fi
