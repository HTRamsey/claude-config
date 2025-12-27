#!/usr/bin/env bash
# benchmark-hooks.sh - Benchmark hook dispatcher performance
#
# Usage:
#   benchmark-hooks.sh          # Full benchmark (dispatchers vs individual)
#   benchmark-hooks.sh quick    # Quick benchmark (dispatchers only)
#   benchmark-hooks.sh compare  # Compare dispatchers vs individual hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"
ITERATIONS="${BENCHMARK_ITERATIONS:-5}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test payloads
PRETOOL_READ='{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.txt"}}'
POSTTOOL_BASH='{"tool_name":"Bash","tool_input":{"command":"ls"},"tool_result":"file1.txt"}'
USERPROMPT='{"user_prompt":"/commit test","transcript_path":"/tmp/fake.jsonl"}'

benchmark_hook() {
    local hook="$1"
    local payload="$2"
    local total=0

    for ((i=0; i<ITERATIONS; i++)); do
        local start end elapsed
        start=$(date +%s%N)
        echo "$payload" | "$hook" >/dev/null 2>&1 || true
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))
        total=$((total + elapsed))
    done

    echo $((total / ITERATIONS))
}

benchmark_sequence() {
    local name="$1"
    shift
    local hooks=("$@")
    local total=0

    for ((i=0; i<ITERATIONS; i++)); do
        local iteration_time=0
        # Clear pycache for cold start simulation
        rm -rf "$HOOKS_DIR/__pycache__" 2>/dev/null || true

        for hook_payload in "${hooks[@]}"; do
            local hook="${hook_payload%%|*}"
            local payload="${hook_payload#*|}"
            local start end elapsed
            start=$(date +%s%N)
            echo "$payload" | PYTHONDONTWRITEBYTECODE=1 "$hook" >/dev/null 2>&1 || true
            end=$(date +%s%N)
            elapsed=$(( (end - start) / 1000000 ))
            iteration_time=$((iteration_time + elapsed))
        done
        total=$((total + iteration_time))
    done

    echo $((total / ITERATIONS))
}

quick_benchmark() {
    echo -e "${CYAN}Quick Hook Benchmark (${ITERATIONS} iterations)${NC}"
    echo "================================================"
    echo ""

    local pre post user total

    echo -n "PreToolUse dispatcher:     "
    pre=$(benchmark_hook "$HOOKS_DIR/pre_tool_dispatcher.py" "$PRETOOL_READ")
    echo "${pre}ms"

    echo -n "PostToolUse dispatcher:    "
    post=$(benchmark_hook "$HOOKS_DIR/post_tool_dispatcher.py" "$POSTTOOL_BASH")
    echo "${post}ms"

    echo -n "UserPromptSubmit dispatcher: "
    user=$(benchmark_hook "$HOOKS_DIR/user_prompt_dispatcher.py" "$USERPROMPT")
    echo "${user}ms"

    total=$((pre + post + user))
    echo ""
    echo -e "${GREEN}Total: ${total}ms${NC}"
}

full_benchmark() {
    echo -e "${CYAN}Full Hook Benchmark - Dispatchers vs Individual${NC}"
    echo "================================================"
    echo "Iterations: $ITERATIONS (set BENCHMARK_ITERATIONS to change)"
    echo ""

    # Individual hooks
    echo -e "${YELLOW}INDIVIDUAL HOOKS (cold start):${NC}"

    local pretool_individual posttool_individual userprompt_individual

    echo -n "  PreToolUse (4 hooks):      "
    pretool_individual=$(benchmark_sequence "pretool" \
        "$HOOKS_DIR/file_protection.py|$PRETOOL_READ" \
        "$HOOKS_DIR/file_monitor.py|$PRETOOL_READ" \
        "$HOOKS_DIR/hierarchical_rules.py|$PRETOOL_READ" \
        "$HOOKS_DIR/suggestion_engine.py|$PRETOOL_READ")
    echo "${pretool_individual}ms"

    echo -n "  PostToolUse (4 hooks):     "
    posttool_individual=$(benchmark_sequence "posttool" \
        "$HOOKS_DIR/tool_success_tracker.py|$POSTTOOL_BASH" \
        "$HOOKS_DIR/output_metrics.py|$POSTTOOL_BASH" \
        "$HOOKS_DIR/build_analyzer.py|$POSTTOOL_BASH" \
        "$HOOKS_DIR/state_saver.py|$POSTTOOL_BASH")
    echo "${posttool_individual}ms"

    echo -n "  UserPromptSubmit (2 hooks): "
    userprompt_individual=$(benchmark_sequence "userprompt" \
        "$HOOKS_DIR/context_monitor.py|$USERPROMPT" \
        "$HOOKS_DIR/usage_tracker.py|$USERPROMPT")
    echo "${userprompt_individual}ms"

    local individual_total=$((pretool_individual + posttool_individual + userprompt_individual))
    echo "  TOTAL:                     ${individual_total}ms"

    echo ""
    echo -e "${YELLOW}DISPATCHERS (cold start):${NC}"

    local pretool_dispatcher posttool_dispatcher userprompt_dispatcher

    echo -n "  PreToolUse (1 dispatcher):  "
    pretool_dispatcher=$(benchmark_sequence "pretool" \
        "$HOOKS_DIR/pre_tool_dispatcher.py|$PRETOOL_READ")
    echo "${pretool_dispatcher}ms"

    echo -n "  PostToolUse (1 dispatcher): "
    posttool_dispatcher=$(benchmark_sequence "posttool" \
        "$HOOKS_DIR/post_tool_dispatcher.py|$POSTTOOL_BASH")
    echo "${posttool_dispatcher}ms"

    echo -n "  UserPromptSubmit (1 disp):  "
    userprompt_dispatcher=$(benchmark_sequence "userprompt" \
        "$HOOKS_DIR/user_prompt_dispatcher.py|$USERPROMPT")
    echo "${userprompt_dispatcher}ms"

    local dispatcher_total=$((pretool_dispatcher + posttool_dispatcher + userprompt_dispatcher))
    echo "  TOTAL:                     ${dispatcher_total}ms"

    # Summary
    echo ""
    echo "================================================"
    echo -e "${GREEN}SUMMARY:${NC}"
    local savings=$((individual_total - dispatcher_total))
    local pct=0
    if [[ $individual_total -gt 0 ]]; then
        pct=$((savings * 100 / individual_total))
    fi
    echo "  Individual: ${individual_total}ms"
    echo "  Dispatchers: ${dispatcher_total}ms"
    echo -e "  ${GREEN}Savings: ${savings}ms (${pct}% faster)${NC}"
    echo ""
    echo "  Per 10-tool conversation: ~$((savings * 10 / 1000)).$((savings * 10 % 1000 / 100))s saved"
}

case "${1:-full}" in
    quick)
        quick_benchmark
        ;;
    compare|full)
        full_benchmark
        ;;
    -h|--help)
        echo "Usage: benchmark-hooks.sh [quick|compare|full]"
        echo ""
        echo "Commands:"
        echo "  quick    Quick benchmark (dispatchers only)"
        echo "  compare  Compare dispatchers vs individual hooks"
        echo "  full     Same as compare (default)"
        echo ""
        echo "Environment:"
        echo "  BENCHMARK_ITERATIONS  Number of iterations (default: 5)"
        ;;
    *)
        full_benchmark
        ;;
esac
