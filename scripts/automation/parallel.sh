#!/usr/bin/env bash
# parallel.sh - Run commands in parallel with proper exit handling
#
# Usage:
#   parallel.sh <max_jobs> <command1> <command2> ...
#   parallel.sh 4 "npm test" "npm run lint" "npm run typecheck"
#   echo -e "cmd1\ncmd2\ncmd3" | parallel.sh 2 -
#
# Options:
#   -q, --quiet     Suppress per-command output, show summary only
#   -f, --fail-fast Exit immediately if any command fails
#   --timeout <sec> Timeout for each command (default: none)
#
# Features:
#   - Runs up to N commands in parallel
#   - Tracks exit codes and timing for each
#   - Proper signal handling (Ctrl-C kills all)
#   - Summary with pass/fail status

SCRIPT_VERSION="1.0.0"

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

# Defaults
MAX_JOBS=4
QUIET=false
FAIL_FAST=false
TIMEOUT=""
COMMANDS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            cat << 'EOF'
parallel.sh - Run commands in parallel with proper exit handling

Usage:
  parallel.sh [options] <max_jobs> <command1> <command2> ...

Options:
  -q, --quiet      Suppress per-command output, show summary only
  -f, --fail-fast  Exit immediately if any command fails
  --timeout <sec>  Timeout for each command (default: none)

Examples:
  # Run 3 test suites in parallel
  parallel.sh 3 "pytest tests/unit" "pytest tests/integration" "pytest tests/e2e"

  # Run linting and type checking
  parallel.sh 2 "npm run lint" "npm run typecheck"

  # Read commands from stdin
  echo -e "make test\nmake lint\nmake docs" | parallel.sh 2 -

  # With timeout
  parallel.sh --timeout 30 4 "curl api1" "curl api2" "curl api3"

EOF
            exit 0
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -f|--fail-fast)
            FAIL_FAST=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -)
            # Read from stdin
            while IFS= read -r line; do
                [[ -n "$line" ]] && COMMANDS+=("$line")
            done
            shift
            ;;
        *)
            if [[ -z "${MAX_JOBS_SET:-}" && "$1" =~ ^[0-9]+$ ]]; then
                MAX_JOBS="$1"
                MAX_JOBS_SET=1
            else
                COMMANDS+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ ${#COMMANDS[@]} -eq 0 ]]; then
    echo "Error: No commands specified" >&2
    echo "Usage: parallel.sh <max_jobs> <command1> <command2> ..." >&2
    exit 1
fi

# Track child processes
declare -A PIDS    # PID -> command
declare -A RESULTS # command -> exit_code
declare -A TIMES   # command -> duration
RUNNING=0
START_TIME=$(date +%s)

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Interrupted. Killing running jobs...${NC}" >&2
    for pid in "${!PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    exit 130
}
trap cleanup INT TERM

# Run a command with optional timeout
run_command() {
    local cmd="$1"
    local cmd_start=$(date +%s)

    if [[ -n "$TIMEOUT" ]]; then
        timeout "$TIMEOUT" bash -c "$cmd" 2>&1
    else
        bash -c "$cmd" 2>&1
    fi
    local exit_code=$?

    local cmd_end=$(date +%s)
    local duration=$((cmd_end - cmd_start))

    echo "___EXIT_CODE___:$exit_code:$duration"
    return $exit_code
}

# Start a job
start_job() {
    local cmd="$1"
    local output_file=$(mktemp "/tmp/parallel-output-$$.XXXXXX")

    run_command "$cmd" > "$output_file" 2>&1 &
    local pid=$!

    PIDS[$pid]="$cmd"
    echo "$output_file" > "/tmp/parallel-$$-$pid"
    ((RUNNING++))

    $QUIET || echo -e "${YELLOW}Started:${NC} $cmd (PID $pid)"
}

# Wait for a job to finish
wait_for_job() {
    local pid=""
    local wait_status=0

    # bash 5.1+ supports wait -n -p to get the finished PID
    if [[ ${BASH_VERSINFO[0]} -ge 5 && ${BASH_VERSINFO[1]} -ge 1 ]]; then
        wait -n -p pid 2>/dev/null || wait_status=$?
    else
        # Fallback for older bash: poll for finished processes
        # More reliable than wait -n which may not be available
        while true; do
            for p in "${!PIDS[@]}"; do
                if ! kill -0 "$p" 2>/dev/null; then
                    pid="$p"
                    # Get exit status via wait
                    wait "$p" 2>/dev/null || wait_status=$?
                    break 2
                fi
            done
            # Small sleep to avoid busy-wait
            sleep 0.1
        done
    fi

    if [[ -n "${PIDS[$pid]:-}" ]]; then
        local cmd="${PIDS[$pid]}"
        local output_file=$(cat "/tmp/parallel-$$-$pid" 2>/dev/null)

        # Parse output for exit code
        local exit_code=0
        local duration=0
        if [[ -f "$output_file" ]]; then
            local last_line=$(tail -1 "$output_file")
            if [[ "$last_line" =~ ___EXIT_CODE___:([0-9]+):([0-9]+) ]]; then
                exit_code="${BASH_REMATCH[1]}"
                duration="${BASH_REMATCH[2]}"
                # Remove the marker line from output
                head -n -1 "$output_file" > "$output_file.clean"
                mv "$output_file.clean" "$output_file"
            fi
        fi

        RESULTS["$cmd"]=$exit_code
        TIMES["$cmd"]=$duration

        if [[ $exit_code -eq 0 ]]; then
            $QUIET || echo -e "${GREEN}✓ Done:${NC} $cmd (${duration}s)"
        else
            echo -e "${RED}✗ Failed:${NC} $cmd (exit $exit_code, ${duration}s)"
            if [[ -f "$output_file" ]] && ! $QUIET; then
                echo "--- Output ---"
                head -50 "$output_file"
                echo "---"
            fi
        fi

        [[ -f "$output_file" ]] && rm -f "$output_file"
        rm -f "/tmp/parallel-$$-$pid"
        unset "PIDS[$pid]"
        ((RUNNING--))

        if $FAIL_FAST && [[ $exit_code -ne 0 ]]; then
            cleanup
            exit $exit_code
        fi
    fi
}

# Main execution
echo "=== Parallel Execution: ${#COMMANDS[@]} commands, max $MAX_JOBS jobs ==="
echo ""

for cmd in "${COMMANDS[@]}"; do
    # Wait if at max capacity
    while [[ $RUNNING -ge $MAX_JOBS ]]; do
        wait_for_job
    done

    start_job "$cmd"
done

# Wait for remaining jobs
while [[ $RUNNING -gt 0 ]]; do
    wait_for_job
done

# Summary
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Summary ==="

passed=0
failed=0
for cmd in "${!RESULTS[@]}"; do
    if [[ ${RESULTS[$cmd]} -eq 0 ]]; then
        ((passed++))
    else
        ((failed++))
    fi
done

echo "  Total: ${#RESULTS[@]} commands"
echo -e "  ${GREEN}Passed: $passed${NC}"
[[ $failed -gt 0 ]] && echo -e "  ${RED}Failed: $failed${NC}"
echo "  Time: ${TOTAL_TIME}s (parallel)"

# Exit with error if any failed
[[ $failed -gt 0 ]] && exit 1
exit 0
