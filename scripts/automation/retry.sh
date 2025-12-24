#!/usr/bin/env bash
# retry.sh - Retry flaky commands with exponential backoff
#
# Usage:
#   retry.sh <max_attempts> <command...>
#   retry.sh 3 curl -s https://api.example.com
#   retry.sh --delay 5 --backoff 2 5 npm install
#
# Options:
#   --delay <sec>     Initial delay between retries (default: 1)
#   --backoff <mult>  Backoff multiplier (default: 2)
#   --max-delay <sec> Maximum delay (default: 60)
#   --on-retry <cmd>  Command to run before each retry

SCRIPT_VERSION="1.0.0"

set -uo pipefail

# Defaults
DELAY=1
BACKOFF=2
MAX_DELAY=60
ON_RETRY=""
MAX_ATTEMPTS=3
QUIET=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    cat << 'EOF'
retry.sh - Retry flaky commands with exponential backoff

Usage:
  retry.sh [options] <max_attempts> <command...>

Options:
  --delay <sec>      Initial delay between retries (default: 1)
  --backoff <mult>   Backoff multiplier (default: 2)
  --max-delay <sec>  Maximum delay cap (default: 60)
  --on-retry <cmd>   Command to run before each retry
  --quiet            Suppress retry messages

Examples:
  # Retry curl 3 times
  retry.sh 3 curl -s https://api.example.com

  # Retry with custom backoff
  retry.sh --delay 2 --backoff 1.5 5 npm install

  # Run cleanup before each retry
  retry.sh --on-retry "rm -rf node_modules" 3 npm install

  # Retry flaky test
  retry.sh 5 pytest tests/flaky_test.py

Backoff schedule (defaults):
  Attempt 1: immediate
  Attempt 2: 1s delay
  Attempt 3: 2s delay
  Attempt 4: 4s delay
  Attempt 5: 8s delay
  (capped at --max-delay)

EOF
    exit 0
}

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        --backoff)
            BACKOFF="$2"
            shift 2
            ;;
        --max-delay)
            MAX_DELAY="$2"
            shift 2
            ;;
        --on-retry)
            ON_RETRY="$2"
            shift 2
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        *)
            if [[ "$1" =~ ^[0-9]+$ && -z "${MAX_ATTEMPTS_SET:-}" ]]; then
                MAX_ATTEMPTS="$1"
                MAX_ATTEMPTS_SET=1
                shift
            else
                break
            fi
            ;;
    esac
done

if [[ $# -eq 0 ]]; then
    echo "Error: No command specified" >&2
    echo "Usage: retry.sh <max_attempts> <command...>" >&2
    exit 1
fi

# Calculate delay with exponential backoff
calc_delay() {
    local attempt="$1"
    local delay

    # Use bc for float math if available, otherwise use integer approximation
    if command -v bc &>/dev/null; then
        delay=$(echo "$DELAY * $BACKOFF ^ ($attempt - 1)" | bc 2>/dev/null)
        # Cap at max delay
        if [[ $(echo "$delay > $MAX_DELAY" | bc 2>/dev/null) -eq 1 ]]; then
            delay=$MAX_DELAY
        fi
    else
        # Integer-only fallback (good enough for most cases)
        delay=$DELAY
        for ((i = 1; i < attempt; i++)); do
            delay=$((delay * BACKOFF))
            [[ $delay -gt $MAX_DELAY ]] && delay=$MAX_DELAY && break
        done
    fi

    # Ensure integer
    printf "%.0f" "$delay"
}

# Main retry loop
attempt=1
last_exit=0

while [[ $attempt -le $MAX_ATTEMPTS ]]; do
    if [[ $attempt -gt 1 ]]; then
        delay=$(calc_delay $attempt)
        echo -e "${YELLOW}Retry $attempt/$MAX_ATTEMPTS in ${delay}s...${NC}" >&2

        # Run on-retry command if specified
        if [[ -n "$ON_RETRY" ]]; then
            echo -e "${YELLOW}Running: $ON_RETRY${NC}" >&2
            eval "$ON_RETRY" || true
        fi

        sleep "$delay"
    fi

    # Run the command
    if [[ $attempt -eq 1 ]]; then
        echo -e "Running: $*" >&2
    fi

    set +e
    "$@"
    last_exit=$?
    set -e

    if [[ $last_exit -eq 0 ]]; then
        if [[ $attempt -gt 1 ]]; then
            echo -e "${GREEN}Succeeded on attempt $attempt${NC}" >&2
        fi
        exit 0
    fi

    echo -e "${RED}Attempt $attempt failed (exit $last_exit)${NC}" >&2
    ((attempt++))
done

echo -e "${RED}All $MAX_ATTEMPTS attempts failed${NC}" >&2
exit $last_exit
