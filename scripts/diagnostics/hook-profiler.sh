#!/usr/bin/env bash
# hook-profiler.sh - Analyze hook execution times from hook-events.jsonl
#
# Usage:
#   hook-profiler.sh [--last N] [--slow N] [--handler NAME]
#
# Options:
#   --last N      Analyze last N entries (default: 1000)
#   --slow N      Show handlers slower than N ms (default: 50)
#   --handler X   Filter to specific handler
#   --summary     Show summary statistics only

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$HOME/.claude/data/hook-events.jsonl"

LAST=1000
SLOW_THRESHOLD=50
HANDLER_FILTER=""
SUMMARY_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --last)
            LAST="$2"
            shift 2
            ;;
        --slow)
            SLOW_THRESHOLD="$2"
            shift 2
            ;;
        --handler)
            HANDLER_FILTER="$2"
            shift 2
            ;;
        --summary)
            SUMMARY_ONLY=true
            shift
            ;;
        -h|--help)
            echo "Usage: hook-profiler.sh [--last N] [--slow N] [--handler NAME]"
            echo ""
            echo "Analyzes hook execution times from hook-events.jsonl"
            echo ""
            echo "Options:"
            echo "  --last N      Analyze last N entries (default: 1000)"
            echo "  --slow N      Show handlers slower than N ms (default: 50)"
            echo "  --handler X   Filter to specific handler"
            echo "  --summary     Show summary statistics only"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

if [[ ! -f "$LOG_FILE" ]]; then
    echo "No log file found: $LOG_FILE"
    exit 1
fi

# Check for jq
if ! command -v jq &>/dev/null; then
    echo "Error: jq required for parsing. Install with: apt install jq"
    exit 1
fi

echo "=== Hook Profiler Report ==="
echo "Analyzing last $LAST timing entries..."
echo ""

# Extract timing data
TIMING_DATA=$(tail -n 10000 "$LOG_FILE" | \
    grep '"handler_timing"' | \
    tail -n "$LAST" | \
    jq -r 'select(.data.elapsed_ms != null) | [.data.handler, .data.elapsed_ms, .data.tool, .data.success] | @tsv' 2>/dev/null)

if [[ -z "$TIMING_DATA" ]]; then
    echo "No timing data found. Hook profiling may not be active yet."
    echo "Timing data is generated after tool calls with the updated dispatchers."
    exit 0
fi

# Filter by handler if specified
if [[ -n "$HANDLER_FILTER" ]]; then
    TIMING_DATA=$(echo "$TIMING_DATA" | grep "^$HANDLER_FILTER	")
fi

# Count entries
TOTAL=$(echo "$TIMING_DATA" | wc -l)
echo "Total timing entries: $TOTAL"
echo ""

# Summary by handler
echo "=== Handler Statistics ==="
echo ""
printf "%-30s %8s %8s %8s %8s\n" "Handler" "Count" "Avg(ms)" "Max(ms)" "P95(ms)"
echo "--------------------------------------------------------------------------------"

echo "$TIMING_DATA" | awk -F'\t' '
{
    handler[$1]++
    sum[$1] += $2
    if ($2 > max[$1]) max[$1] = $2
    times[$1, handler[$1]] = $2
}
END {
    for (h in handler) {
        avg = sum[h] / handler[h]

        # Calculate P95 (approximate)
        n = handler[h]
        p95_idx = int(n * 0.95)
        if (p95_idx < 1) p95_idx = 1

        # Sort times for this handler
        for (i = 1; i <= n; i++) {
            sorted[i] = times[h, i]
        }
        for (i = 1; i <= n; i++) {
            for (j = i + 1; j <= n; j++) {
                if (sorted[i] > sorted[j]) {
                    tmp = sorted[i]
                    sorted[i] = sorted[j]
                    sorted[j] = tmp
                }
            }
        }
        p95 = sorted[p95_idx]

        printf "%-30s %8d %8.1f %8.1f %8.1f\n", h, handler[h], avg, max[h], p95
    }
}' | sort -t$'\t' -k3 -rn

echo ""

# Slow calls
if [[ "$SUMMARY_ONLY" != "true" ]]; then
    SLOW_COUNT=$(echo "$TIMING_DATA" | awk -F'\t' -v thresh="$SLOW_THRESHOLD" '$2 > thresh' | wc -l)

    if [[ "$SLOW_COUNT" -gt 0 ]]; then
        echo "=== Slow Calls (>${SLOW_THRESHOLD}ms) ==="
        echo ""
        printf "%-30s %8s %10s\n" "Handler" "Time(ms)" "Tool"
        echo "----------------------------------------------------"
        echo "$TIMING_DATA" | awk -F'\t' -v thresh="$SLOW_THRESHOLD" '
            $2 > thresh { printf "%-30s %8.1f %10s\n", $1, $2, $3 }
        ' | sort -t$'\t' -k2 -rn | head -20
        echo ""
        echo "Total slow calls: $SLOW_COUNT / $TOTAL ($(echo "scale=1; $SLOW_COUNT * 100 / $TOTAL" | bc)%)"
    else
        echo "No calls slower than ${SLOW_THRESHOLD}ms found."
    fi
    echo ""
fi

# Error rate
ERROR_COUNT=$(echo "$TIMING_DATA" | awk -F'\t' '$4 == "false"' | wc -l)
if [[ "$ERROR_COUNT" -gt 0 ]]; then
    echo "=== Errors ==="
    echo "Failed handler calls: $ERROR_COUNT / $TOTAL"
    echo ""
fi

# Per-tool breakdown
echo "=== By Tool ==="
echo ""
printf "%-15s %8s %8s\n" "Tool" "Calls" "Avg(ms)"
echo "--------------------------------------"
echo "$TIMING_DATA" | awk -F'\t' '
{
    tool[$3]++
    sum[$3] += $2
}
END {
    for (t in tool) {
        avg = sum[t] / tool[t]
        printf "%-15s %8d %8.1f\n", t, tool[t], avg
    }
}' | sort -t$'\t' -k2 -rn
