#!/usr/bin/env bash
# Batch annotation helper - prepare multiple items for single-prompt processing
# Formats items for efficient batch prompting (30%+ token savings)
#
# Usage:
#   batch-annotate.sh <files...>
#   find . -name "*.py" | batch-annotate.sh -
#
# Output format suitable for batch processing in a single prompt

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
