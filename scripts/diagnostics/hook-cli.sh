#!/usr/bin/env bash
# Hook management CLI for Claude Code
# Usage: hook-cli.sh <command> [args]
#
# Commands:
#   list              List all hooks and their status
#   status [hook]     Show detailed status for a hook or all hooks
#   enable <hook>     Enable a disabled hook
#   disable <hook>    Disable a hook
#   test <hook>       Test a hook with sample input
#   bench [hook]      Benchmark hook latency
#   logs [hook]       Show recent log entries for a hook

set -euo pipefail

HOOKS_DIR="${HOME}/.claude/hooks"
DATA_DIR="${HOME}/.claude/data"
CONFIG_FILE="${DATA_DIR}/hook-config.json"
LOG_FILE="${DATA_DIR}/hook-events.jsonl"
SETTINGS_FILE="${HOME}/.claude/settings.json"
VENV_PYTHON="${HOME}/.claude/venv/bin/python3"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    cat <<EOF
Hook Management CLI

Usage: $(basename "$0") <command> [args]

Commands:
  list              List all hooks and their status
  status [hook]     Show detailed status (last run, errors, latency)
  enable <hook>     Enable a disabled hook
  disable <hook>    Disable a hook (won't be called by dispatchers)
  test <hook>       Test a hook with sample input
  bench [hook]      Benchmark hook latency (run 5 times)
  logs [hook]       Show recent log entries (last 20)

Examples:
  $(basename "$0") list
  $(basename "$0") status file_protection
  $(basename "$0") disable tdd_guard
  $(basename "$0") test dangerous_command_blocker
  $(basename "$0") bench
EOF
}

# Ensure config file exists
ensure_config() {
    mkdir -p "$DATA_DIR"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo '{"disabled": [], "updated": ""}' > "$CONFIG_FILE"
    fi
}

# Get list of all hooks
get_all_hooks() {
    # Python hooks
    find "$HOOKS_DIR" -maxdepth 1 -name "*.py" -type f 2>/dev/null | while read -r f; do
        basename "$f" .py
    done
    # Shell hooks
    find "$HOOKS_DIR" -maxdepth 1 -name "*.sh" -type f 2>/dev/null | while read -r f; do
        basename "$f" .sh
    done
}

# Check if hook is disabled
is_disabled() {
    local hook="$1"
    ensure_config
    jq -r --arg h "$hook" '.disabled | index($h) != null' "$CONFIG_FILE" 2>/dev/null || echo "false"
}

# Get hook file path
get_hook_path() {
    local hook="$1"
    if [[ -f "${HOOKS_DIR}/${hook}.py" ]]; then
        echo "${HOOKS_DIR}/${hook}.py"
    elif [[ -f "${HOOKS_DIR}/${hook}.sh" ]]; then
        echo "${HOOKS_DIR}/${hook}.sh"
    else
        echo ""
    fi
}

# Get hook type (dispatcher, standalone, helper)
get_hook_type() {
    local hook="$1"
    case "$hook" in
        pre_tool_dispatcher|post_tool_dispatcher)
            echo "dispatcher"
            ;;
        hook_utils|hook_sdk)
            echo "library"
            ;;
        *_async)
            echo "async"
            ;;
        *)
            echo "handler"
            ;;
    esac
}

# List all hooks
cmd_list() {
    echo -e "${BLUE}Hooks in ${HOOKS_DIR}${NC}"
    echo ""
    printf "%-30s %-12s %-10s %s\n" "HOOK" "TYPE" "STATUS" "FILE"
    printf "%-30s %-12s %-10s %s\n" "----" "----" "------" "----"

    get_all_hooks | sort | while read -r hook; do
        local path
        path=$(get_hook_path "$hook")
        local hook_type
        hook_type=$(get_hook_type "$hook")
        local status="enabled"
        local status_color="$GREEN"

        if [[ $(is_disabled "$hook") == "true" ]]; then
            status="disabled"
            status_color="$RED"
        fi

        # Libraries are always "n/a"
        if [[ "$hook_type" == "library" ]]; then
            status="n/a"
            status_color="$YELLOW"
        fi

        local ext="${path##*.}"
        printf "%-30s %-12s ${status_color}%-10s${NC} %s\n" "$hook" "$hook_type" "$status" "${hook}.${ext}"
    done

    echo ""
    echo -e "${YELLOW}Tip:${NC} Use 'hook-cli.sh status <hook>' for details"
}

# Show status of a hook
cmd_status() {
    local hook="${1:-}"

    if [[ -z "$hook" ]]; then
        # Show summary for all hooks
        echo -e "${BLUE}Hook Status Summary${NC}"
        echo ""

        local total=0
        local enabled=0
        local disabled=0
        local errors=0

        get_all_hooks | while read -r h; do
            ((total++)) || true
            if [[ $(is_disabled "$h") == "true" ]]; then
                ((disabled++)) || true
            else
                ((enabled++)) || true
            fi
        done

        # Count errors in last 100 log entries
        if [[ -f "$LOG_FILE" ]]; then
            errors=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -c '"level":"error"' || echo "0")
        fi

        echo "Total hooks: $(get_all_hooks | wc -l)"
        echo "Enabled: $(get_all_hooks | while read -r h; do [[ $(is_disabled "$h") != "true" ]] && echo "$h"; done | wc -l)"
        echo "Disabled: $(get_all_hooks | while read -r h; do [[ $(is_disabled "$h") == "true" ]] && echo "$h"; done | wc -l)"
        echo "Recent errors (last 100 events): $errors"
        return
    fi

    # Show detailed status for specific hook
    local path
    path=$(get_hook_path "$hook")
    if [[ -z "$path" ]]; then
        echo -e "${RED}Error: Hook '$hook' not found${NC}" >&2
        exit 1
    fi

    echo -e "${BLUE}Status: ${hook}${NC}"
    echo ""
    echo "File: $path"
    echo "Type: $(get_hook_type "$hook")"
    echo "Status: $(is_disabled "$hook" | sed 's/true/disabled/' | sed 's/false/enabled/')"
    echo "Size: $(wc -c < "$path") bytes"
    echo "Modified: $(stat -c '%y' "$path" 2>/dev/null | cut -d. -f1)"

    # Recent log entries
    if [[ -f "$LOG_FILE" ]]; then
        echo ""
        echo "Recent events (last 5):"
        grep "\"hook\":\"$hook\"" "$LOG_FILE" 2>/dev/null | tail -5 | while read -r line; do
            local ts event level
            ts=$(echo "$line" | jq -r '.timestamp' 2>/dev/null | cut -d. -f1)
            event=$(echo "$line" | jq -r '.event' 2>/dev/null)
            level=$(echo "$line" | jq -r '.level' 2>/dev/null)
            echo "  $ts - $event ($level)"
        done
    fi
}

# Enable a hook
cmd_enable() {
    local hook="$1"

    if [[ -z "$hook" ]]; then
        echo -e "${RED}Error: Hook name required${NC}" >&2
        usage
        exit 1
    fi

    local path
    path=$(get_hook_path "$hook")
    if [[ -z "$path" ]]; then
        echo -e "${RED}Error: Hook '$hook' not found${NC}" >&2
        exit 1
    fi

    ensure_config
    local current
    current=$(jq -r '.disabled | index("'"$hook"'")' "$CONFIG_FILE" 2>/dev/null)

    if [[ "$current" == "null" ]]; then
        echo -e "${YELLOW}Hook '$hook' is already enabled${NC}"
        return
    fi

    # Remove from disabled list
    jq --arg h "$hook" '.disabled = (.disabled | map(select(. != $h))) | .updated = now | todate' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

    echo -e "${GREEN}Enabled hook: $hook${NC}"
}

# Disable a hook
cmd_disable() {
    local hook="$1"

    if [[ -z "$hook" ]]; then
        echo -e "${RED}Error: Hook name required${NC}" >&2
        usage
        exit 1
    fi

    local path
    path=$(get_hook_path "$hook")
    if [[ -z "$path" ]]; then
        echo -e "${RED}Error: Hook '$hook' not found${NC}" >&2
        exit 1
    fi

    # Don't allow disabling critical hooks
    case "$hook" in
        pre_tool_dispatcher|post_tool_dispatcher|hook_utils|hook_sdk)
            echo -e "${RED}Error: Cannot disable core hook: $hook${NC}" >&2
            exit 1
            ;;
    esac

    ensure_config
    local current
    current=$(is_disabled "$hook")

    if [[ "$current" == "true" ]]; then
        echo -e "${YELLOW}Hook '$hook' is already disabled${NC}"
        return
    fi

    # Add to disabled list
    jq --arg h "$hook" '.disabled = (.disabled + [$h] | unique) | .updated = now | todate' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

    echo -e "${GREEN}Disabled hook: $hook${NC}"
}

# Test a hook
cmd_test() {
    local hook="$1"

    if [[ -z "$hook" ]]; then
        echo -e "${RED}Error: Hook name required${NC}" >&2
        usage
        exit 1
    fi

    local path
    path=$(get_hook_path "$hook")
    if [[ -z "$path" ]]; then
        echo -e "${RED}Error: Hook '$hook' not found${NC}" >&2
        exit 1
    fi

    echo -e "${BLUE}Testing hook: $hook${NC}"
    echo ""

    # Generate sample input based on hook type
    local sample_input
    case "$hook" in
        file_protection|file_monitor|state_saver)
            sample_input='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.txt","new_string":"test"}}'
            ;;
        dangerous_command_blocker)
            sample_input='{"tool_name":"Bash","tool_input":{"command":"echo hello"}}'
            ;;
        suggestion_engine|tdd_guard)
            sample_input='{"tool_name":"Write","tool_input":{"file_path":"/tmp/test.py","content":"def foo(): pass"}}'
            ;;
        batch_operation_detector)
            sample_input='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.py","old_string":"foo","new_string":"bar"},"tool_result":{}}'
            ;;
        unified_cache)
            sample_input='{"tool_name":"Task","tool_input":{"prompt":"test","subagent_type":"Explore"},"tool_result":{"output":"test result"}}'
            ;;
        *)
            sample_input='{"tool_name":"Bash","tool_input":{"command":"echo test"},"tool_result":{"exit_code":0,"stdout":"test"}}'
            ;;
    esac

    echo "Input: $sample_input"
    echo ""
    echo "Output:"

    local start end elapsed
    start=$(date +%s%3N)

    if [[ "$path" == *.py ]]; then
        echo "$sample_input" | "$VENV_PYTHON" "$path" 2>&1 || true
    else
        echo "$sample_input" | bash "$path" 2>&1 || true
    fi

    end=$(date +%s%3N)
    elapsed=$((end - start))

    echo ""
    echo -e "${GREEN}Completed in ${elapsed}ms${NC}"
}

# Benchmark hooks
cmd_bench() {
    local hook="${1:-}"
    local iterations=5

    echo -e "${BLUE}Hook Benchmark${NC}"
    echo ""

    if [[ -n "$hook" ]]; then
        # Benchmark single hook
        local path
        path=$(get_hook_path "$hook")
        if [[ -z "$path" ]]; then
            echo -e "${RED}Error: Hook '$hook' not found${NC}" >&2
            exit 1
        fi

        echo "Hook: $hook"
        echo "Iterations: $iterations"
        echo ""

        local total=0
        local sample_input='{"tool_name":"Bash","tool_input":{"command":"echo test"}}'

        for i in $(seq 1 $iterations); do
            local start end elapsed
            start=$(date +%s%3N)

            if [[ "$path" == *.py ]]; then
                echo "$sample_input" | "$VENV_PYTHON" "$path" >/dev/null 2>&1 || true
            else
                echo "$sample_input" | bash "$path" >/dev/null 2>&1 || true
            fi

            end=$(date +%s%3N)
            elapsed=$((end - start))
            total=$((total + elapsed))
            echo "  Run $i: ${elapsed}ms"
        done

        local avg=$((total / iterations))
        echo ""
        echo "Average: ${avg}ms"
    else
        # Benchmark all hooks
        printf "%-30s %10s\n" "HOOK" "AVG (ms)"
        printf "%-30s %10s\n" "----" "--------"

        get_all_hooks | sort | while read -r h; do
            local path
            path=$(get_hook_path "$h")
            local hook_type
            hook_type=$(get_hook_type "$h")

            # Skip libraries
            if [[ "$hook_type" == "library" ]]; then
                continue
            fi

            local total=0
            local sample_input='{"tool_name":"Bash","tool_input":{"command":"echo test"}}'

            for _ in $(seq 1 $iterations); do
                local start end elapsed
                start=$(date +%s%3N)

                if [[ "$path" == *.py ]]; then
                    echo "$sample_input" | timeout 5 "$VENV_PYTHON" "$path" >/dev/null 2>&1 || true
                else
                    echo "$sample_input" | timeout 5 bash "$path" >/dev/null 2>&1 || true
                fi

                end=$(date +%s%3N)
                elapsed=$((end - start))
                total=$((total + elapsed))
            done

            local avg=$((total / iterations))
            printf "%-30s %10d\n" "$h" "$avg"
        done
    fi
}

# Show logs for a hook
cmd_logs() {
    local hook="${1:-}"
    local count=20

    if [[ ! -f "$LOG_FILE" ]]; then
        echo -e "${YELLOW}No log file found${NC}"
        return
    fi

    if [[ -n "$hook" ]]; then
        echo -e "${BLUE}Logs for: $hook (last $count)${NC}"
        echo ""
        grep "\"hook\":\"$hook\"" "$LOG_FILE" 2>/dev/null | tail -"$count" | while read -r line; do
            local ts event level data
            ts=$(echo "$line" | jq -r '.timestamp' 2>/dev/null | cut -d. -f1)
            event=$(echo "$line" | jq -r '.event' 2>/dev/null)
            level=$(echo "$line" | jq -r '.level' 2>/dev/null)
            data=$(echo "$line" | jq -c '.data' 2>/dev/null)
            echo "$ts [$level] $event: $data"
        done
    else
        echo -e "${BLUE}All hook logs (last $count)${NC}"
        echo ""
        tail -"$count" "$LOG_FILE" | while read -r line; do
            local ts hook event level
            ts=$(echo "$line" | jq -r '.timestamp' 2>/dev/null | cut -d. -f1)
            hook=$(echo "$line" | jq -r '.hook' 2>/dev/null)
            event=$(echo "$line" | jq -r '.event' 2>/dev/null)
            level=$(echo "$line" | jq -r '.level' 2>/dev/null)
            echo "$ts [$hook] $event ($level)"
        done
    fi
}

# Main
main() {
    local cmd="${1:-}"

    case "$cmd" in
        list)
            cmd_list
            ;;
        status)
            cmd_status "${2:-}"
            ;;
        enable)
            cmd_enable "${2:-}"
            ;;
        disable)
            cmd_disable "${2:-}"
            ;;
        test)
            cmd_test "${2:-}"
            ;;
        bench|benchmark)
            cmd_bench "${2:-}"
            ;;
        logs|log)
            cmd_logs "${2:-}"
            ;;
        -h|--help|help|"")
            usage
            ;;
        *)
            echo -e "${RED}Unknown command: $cmd${NC}" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
