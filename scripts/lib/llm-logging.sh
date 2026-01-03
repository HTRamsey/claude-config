#!/usr/bin/env bash
# LLM Routing Logger
# Dual logging: detailed JSONL + hook-events summary
#
# Usage (source in other scripts):
#   source ~/.claude/scripts/lib/llm-logging.sh
#   log_routing "gemini" "summarize this" "success" "large_context" 3500
#   log_routing "codex" "generate API" "failed" "auth_error"

set -euo pipefail

# Log locations
LLM_LOG_DIR="${HOME}/.claude/data/logs"
LLM_LOG_FILE="${LLM_LOG_DIR}/llm-routing.jsonl"
HOOK_EVENTS_FILE="${HOME}/.claude/data/hook-events.jsonl"

# Ensure log directory exists
mkdir -p "$LLM_LOG_DIR"

# Log a routing decision
# Args: provider, prompt, status, reason, [latency_ms]
log_routing() {
    local provider="${1:-unknown}"
    local prompt="${2:-}"
    local status="${3:-unknown}"
    local reason="${4:-}"
    local latency_ms="${5:-0}"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Truncate prompt for logging (first 100 chars)
    local prompt_preview="${prompt:0:100}"
    # Escape special characters for JSON
    prompt_preview=$(echo "$prompt_preview" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' ')

    # Detailed log entry
    local detailed_entry
    detailed_entry=$(cat <<EOF
{"timestamp":"${timestamp}","provider":"${provider}","prompt":"${prompt_preview}","status":"${status}","reason":"${reason}","latency_ms":${latency_ms}}
EOF
)
    echo "$detailed_entry" >> "$LLM_LOG_FILE"

    # Summary entry for hook-events
    local summary_entry
    summary_entry=$(cat <<EOF
{"timestamp":"${timestamp}","event":"llm_routing","provider":"${provider}","status":"${status}"}
EOF
)
    echo "$summary_entry" >> "$HOOK_EVENTS_FILE"
}

# Log routing attempt (before invocation)
log_attempt() {
    local provider="${1:-unknown}"
    local prompt="${2:-}"
    local reason="${3:-}"
    log_routing "$provider" "$prompt" "attempting" "$reason" 0
}

# Log routing success (after successful invocation)
log_success() {
    local provider="${1:-unknown}"
    local prompt="${2:-}"
    local reason="${3:-}"
    local latency_ms="${4:-0}"
    log_routing "$provider" "$prompt" "success" "$reason" "$latency_ms"
}

# Log routing failure (after failed invocation)
log_failure() {
    local provider="${1:-unknown}"
    local prompt="${2:-}"
    local reason="${3:-}"
    local latency_ms="${4:-0}"
    log_routing "$provider" "$prompt" "failed" "$reason" "$latency_ms"
}

# Log fallback (when switching to next provider)
log_fallback() {
    local from_provider="${1:-unknown}"
    local to_provider="${2:-unknown}"
    local prompt="${3:-}"
    local reason="${4:-}"
    log_routing "$to_provider" "$prompt" "fallback" "from_${from_provider}:${reason}" 0
}

# Get recent routing decisions
# Args: [count] (default 10)
get_recent_routing() {
    local count="${1:-10}"
    if [[ -f "$LLM_LOG_FILE" ]]; then
        tail -n "$count" "$LLM_LOG_FILE"
    fi
}

# Get routing stats for today
get_today_stats() {
    local today
    today=$(date -u +"%Y-%m-%d")

    if [[ ! -f "$LLM_LOG_FILE" ]]; then
        echo "{}"
        return
    fi

    awk -v today="$today" '
        BEGIN { FS="[,:\"]+"; gemini=0; codex=0; copilot=0; claude=0; success=0; failed=0 }
        $0 ~ today {
            for (i=1; i<=NF; i++) {
                if ($i == "provider") provider=$(i+1)
                if ($i == "status") status=$(i+1)
            }
            if (provider == "gemini") gemini++
            if (provider == "codex") codex++
            if (provider == "copilot") copilot++
            if (provider == "claude") claude++
            if (status == "success") success++
            if (status == "failed") failed++
        }
        END {
            total = gemini + codex + copilot + claude
            printf "{\"date\":\"%s\",\"total\":%d,\"success\":%d,\"failed\":%d,\"gemini\":%d,\"codex\":%d,\"copilot\":%d,\"claude\":%d}\n", today, total, success, failed, gemini, codex, copilot, claude
        }
    ' "$LLM_LOG_FILE"
}

# Rotate log if too large (>10MB)
rotate_log_if_needed() {
    local max_size=$((10 * 1024 * 1024))  # 10MB

    if [[ -f "$LLM_LOG_FILE" ]]; then
        local size
        size=$(stat -f%z "$LLM_LOG_FILE" 2>/dev/null || stat -c%s "$LLM_LOG_FILE" 2>/dev/null || echo 0)

        if [[ "$size" -gt "$max_size" ]]; then
            local backup="${LLM_LOG_FILE}.$(date +%Y%m%d-%H%M%S).bak"
            mv "$LLM_LOG_FILE" "$backup"
            # Keep last 1000 entries in new file
            tail -n 1000 "$backup" > "$LLM_LOG_FILE"
            # Compress backup
            gzip "$backup" 2>/dev/null || true
        fi
    fi
}

# CLI interface when run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        log)
            shift
            log_routing "$@"
            ;;
        recent)
            get_recent_routing "${2:-10}"
            ;;
        stats)
            get_today_stats
            ;;
        rotate)
            rotate_log_if_needed
            echo "Log rotation check complete"
            ;;
        -h|--help|help)
            cat <<EOF
LLM Routing Logger

Usage:
  Source in scripts:
    source ~/.claude/scripts/lib/llm-logging.sh
    log_routing "provider" "prompt" "status" "reason" latency_ms

  CLI commands:
    llm-logging.sh log <provider> <prompt> <status> <reason> [latency_ms]
    llm-logging.sh recent [count]     Show recent routing decisions
    llm-logging.sh stats              Show today's routing stats
    llm-logging.sh rotate             Rotate log if >10MB

Log files:
  Detailed: ~/.claude/data/logs/llm-routing.jsonl
  Summary:  ~/.claude/data/hook-events.jsonl
EOF
            ;;
        *)
            echo "Usage: llm-logging.sh {log|recent|stats|rotate|help}"
            exit 1
            ;;
    esac
fi
