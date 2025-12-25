#!/usr/bin/env bash
set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh" 2>/dev/null || source "$HOME/.claude/scripts/lib/common.sh"

usage() {
    cat << 'EOF'
Usage: batch-annotate.sh <files...>
       find . -name "*.py" | batch-annotate.sh -

Batch annotation helper - prepare multiple items for single-prompt processing.
Formats items for efficient batch prompting (30%+ token savings).

Options:
  -h, --help    Show this help

Examples:
  batch-annotate.sh file1.py file2.py file3.py
  find . -name "*.py" | batch-annotate.sh -
  fd -e ts | batch-annotate.sh -
EOF
    exit 0
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

ITEMS=()

if [[ "$1" == "-" ]]; then
    while IFS= read -r line; do
        [[ -n "$line" ]] && ITEMS+=("$line")
    done
else
    ITEMS=("$@")
fi

TOTAL=${#ITEMS[@]}

echo "=== Batch Annotation ($TOTAL items) ==="
echo ""
echo "Process these items together in a single response:"
echo ""

idx=1
for item in "${ITEMS[@]}"; do
    if [[ -f "$item" ]]; then
        # File - show first 50 lines with item number
        echo "[$idx] FILE: $item"
        echo '```'
        head -50 "$item"
        lines=$(wc -l < "$item")
        if [[ $lines -gt 50 ]]; then
            echo "... ($((lines - 50)) more lines)"
        fi
        echo '```'
    else
        # Plain text item
        echo "[$idx] $item"
    fi
    echo ""
    ((idx++))
done

echo "---"
echo "Respond with results for each item [1]-[$TOTAL] in a single response."
