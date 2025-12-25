#!/usr/bin/env bash
# hook-benchmark.sh - Profile hook execution latency
# Usage: hook-benchmark.sh [--save] [--compare FILE]
#
# Options:
#   --save      Save results to data/hook-latency.json
#   --compare   Compare against previous baseline

set -euo pipefail

# Load common utilities
source "$(dirname "$0")/../lib/common.sh"

HOOKS_DIR="$HOME/.claude/hooks"
DATA_DIR="$HOME/.claude/data"
BASELINE_FILE="$DATA_DIR/hook-latency.json"

SAVE=false
COMPARE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --save) SAVE=true; shift ;;
        --compare) COMPARE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: hook-benchmark.sh [--save] [--compare FILE]"
            exit 0
            ;;
        *) shift ;;
    esac
done

echo "=== Hook Latency Benchmark ==="
echo "Date: $(date)"
echo ""

# Sample contexts for different hook types
PRETOOL_CONTEXT='{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.txt"}}'
POSTTOOL_CONTEXT='{"tool_name":"Bash","tool_input":{"command":"echo test"},"tool_result":"test"}'
USERPROMPT_CONTEXT='{"prompt":"test prompt","session_id":"test"}'

declare -A RESULTS

benchmark_hook() {
    local hook="$1"
    local context="$2"
    local name=$(basename "$hook" .py)

    # Skip utility files
    [[ "$name" == "hook_utils" ]] && return
    [[ "$name" == "__pycache__" ]] && return

    # Run 3 times and take median
    local times=()
    for i in 1 2 3; do
        local start=$(date +%s%3N)
        echo "$context" | timeout 2 python3 "$hook" >/dev/null 2>&1 || true
        local end=$(date +%s%3N)
        times+=($((end - start)))
    done

    # Sort and get median
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}")); unset IFS
    local median=${sorted[1]}

    RESULTS["$name"]=$median

    # Color based on latency
    local color="$GREEN"
    [[ $median -gt 50 ]] && color="$YELLOW"
    [[ $median -gt 100 ]] && color="$RED"

    printf "  %-35s ${color}%4dms${NC}\n" "$name" "$median"
}

echo "## PreToolUse Hooks"
for hook in "$HOOKS_DIR"/*.py; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook" .py)
    # Check if it's a PreToolUse hook by looking for permissionDecision
    if grep -q "permissionDecision\|PreToolUse" "$hook" 2>/dev/null; then
        benchmark_hook "$hook" "$PRETOOL_CONTEXT"
    fi
done
echo ""

echo "## PostToolUse Hooks"
for hook in "$HOOKS_DIR"/*.py; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook" .py)
    if grep -q "PostToolUse\|tool_result" "$hook" 2>/dev/null && ! grep -q "permissionDecision" "$hook" 2>/dev/null; then
        benchmark_hook "$hook" "$POSTTOOL_CONTEXT"
    fi
done
echo ""

echo "## Other Hooks"
for hook in "$HOOKS_DIR"/*.py; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook" .py)
    # Skip already benchmarked and utilities
    [[ "$name" == "hook_utils" ]] && continue
    [[ -n "${RESULTS[$name]}" ]] && continue
    benchmark_hook "$hook" "$USERPROMPT_CONTEXT"
done
echo ""

# Calculate totals
total=0
count=0
slow_hooks=()
for name in "${!RESULTS[@]}"; do
    latency=${RESULTS[$name]}
    total=$((total + latency))
    count=$((count + 1))
    [[ $latency -gt 50 ]] && slow_hooks+=("$name:${latency}ms")
done

echo "## Summary"
echo "  Total hooks:    $count"
echo "  Combined:       ${total}ms"
[[ $count -gt 0 ]] && echo "  Average:        $((total / count))ms"
echo ""

if [[ ${#slow_hooks[@]} -gt 0 ]]; then
    echo -e "${YELLOW}## Slow Hooks (>50ms)${NC}"
    for h in "${slow_hooks[@]}"; do
        echo "  - $h"
    done
    echo ""
fi

# Save results
if [[ "$SAVE" == true ]]; then
    mkdir -p "$DATA_DIR"
    echo "{" > "$BASELINE_FILE"
    echo '  "timestamp": "'$(date -Iseconds)'",' >> "$BASELINE_FILE"
    echo '  "hooks": {' >> "$BASELINE_FILE"
    first=true
    for name in "${!RESULTS[@]}"; do
        [[ "$first" == true ]] || echo "," >> "$BASELINE_FILE"
        echo -n "    \"$name\": ${RESULTS[$name]}" >> "$BASELINE_FILE"
        first=false
    done
    echo "" >> "$BASELINE_FILE"
    echo "  }" >> "$BASELINE_FILE"
    echo "}" >> "$BASELINE_FILE"
    echo "Results saved to $BASELINE_FILE"
fi

# Compare to baseline
if [[ -n "$COMPARE" && -f "$COMPARE" ]]; then
    echo ""
    echo "## Comparison to $(basename "$COMPARE")"
    if has_jq; then
        for name in "${!RESULTS[@]}"; do
            old=$(jq -r ".hooks.\"$name\" // empty" "$COMPARE" 2>/dev/null)
            if [[ -n "$old" ]]; then
                new=${RESULTS[$name]}
                diff=$((new - old))
                if [[ $diff -gt 10 ]]; then
                    echo -e "  $name: ${old}ms → ${new}ms ${RED}(+${diff}ms)${NC}"
                elif [[ $diff -lt -10 ]]; then
                    echo -e "  $name: ${old}ms → ${new}ms ${GREEN}(${diff}ms)${NC}"
                fi
            fi
        done
    else
        echo "  Install jq for comparison"
    fi
fi
