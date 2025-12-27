#!/usr/bin/env bash
# Task Queue - Lightweight task queue for Claude Code agents
# Usage: task-queue.sh <command> [args]

SCRIPT_VERSION="1.0.0"

set -euo pipefail

# Source local env (API keys, etc.) if present
[[ -f "${HOME}/.claude/.env.local" ]] && source "${HOME}/.claude/.env.local"

QUEUE_FILE="${HOME}/.claude/data/task-queue.json"
LOCK_FILE="${HOME}/.claude/data/task-queue.lock"
MAX_PARALLEL="${MAX_PARALLEL:-3}"

# Initialize queue file if missing
[[ -f "$QUEUE_FILE" ]] || echo '{"tasks":[],"completed":[]}' > "$QUEUE_FILE"

# Helpers
now() { date +%s; }
uuid() { cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen || echo "task-$(now)-$$"; }

jq_update() {
    local tmp=$(mktemp)
    jq "$@" "$QUEUE_FILE" > "$tmp" && mv "$tmp" "$QUEUE_FILE"
}

usage() {
    cat <<EOF
Task Queue - Manage Claude Code agent tasks

Usage: task-queue.sh <command> [args]

Commands:
  add <prompt> [--agent TYPE] [--after ID] [--priority N] [--worktree] [--mode cli|api] [--model haiku|sonnet|opus]
      Add a task to the queue (--mode api uses direct Anthropic API)

  list [--status STATUS] [--json]
      List tasks (STATUS: pending|running|done|failed|all)

  run [--once] [--max N]
      Process queue (--once: single task, --max: limit concurrent)

  status [ID]
      Show queue status or specific task details

  cancel <ID>
      Cancel a pending task

  retry <ID>
      Retry a failed task

  clear [--completed|--failed|--all]
      Clear tasks from queue

Examples:
  task-queue.sh add "Review auth module" --agent code-reviewer
  task-queue.sh add "Generate tests" --after abc123 --agent test-generator
  task-queue.sh add "Summarize this code" --mode api --model haiku
  task-queue.sh run --max 3
  task-queue.sh list --status running
EOF
}

cmd_add() {
    local prompt="" agent="Explore" after="" priority=5 worktree=false mode="cli" model="sonnet"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent) agent="$2"; shift 2 ;;
            --after) after="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --worktree) worktree=true; shift ;;
            --mode) mode="$2"; shift 2 ;;
            --model) model="$2"; shift 2 ;;
            --*) echo "Unknown option: $1" >&2; exit 1 ;;
            *) prompt="$1"; shift ;;
        esac
    done

    [[ -z "$prompt" ]] && { echo "Error: prompt required" >&2; exit 1; }
    [[ "$mode" != "cli" && "$mode" != "api" ]] && { echo "Error: mode must be 'cli' or 'api'" >&2; exit 1; }
    [[ "$mode" == "api" && ! "$model" =~ ^(haiku|sonnet|opus)$ ]] && { echo "Error: model must be haiku, sonnet, or opus" >&2; exit 1; }

    local id=$(uuid)
    local task=$(jq -n \
        --arg id "$id" \
        --arg prompt "$prompt" \
        --arg agent "$agent" \
        --arg after "$after" \
        --argjson priority "$priority" \
        --argjson worktree "$worktree" \
        --arg mode "$mode" \
        --arg model "$model" \
        --argjson created "$(now)" \
        '{
            id: $id,
            prompt: $prompt,
            agent: $agent,
            after: (if $after == "" then null else $after end),
            priority: $priority,
            worktree: $worktree,
            mode: $mode,
            model: $model,
            status: "pending",
            created: $created,
            started: null,
            completed: null,
            retries: 0,
            max_retries: 2,
            error: null
        }')

    jq_update --argjson task "$task" '.tasks += [$task]'
    echo "$id"
}

cmd_list() {
    local status="pending" json=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status) status="$2"; shift 2 ;;
            --json) json=true; shift ;;
            *) shift ;;
        esac
    done

    local filter='.tasks'
    [[ "$status" != "all" ]] && filter=".tasks | map(select(.status == \"$status\"))"

    if $json; then
        jq "$filter" "$QUEUE_FILE"
    else
        jq -r "$filter | .[] | \"\(.status | .[0:4])\t\(.id | .[0:8])\t\(.agent)\t\(.prompt | .[0:50])\"" "$QUEUE_FILE" | \
            column -t -s $'\t' 2>/dev/null || cat
    fi
}

cmd_status() {
    local id="${1:-}"

    if [[ -z "$id" ]]; then
        # Overall status
        jq -r '{
            pending: [.tasks[] | select(.status == "pending")] | length,
            running: [.tasks[] | select(.status == "running")] | length,
            done: [.tasks[] | select(.status == "done")] | length,
            failed: [.tasks[] | select(.status == "failed")] | length,
            total: .tasks | length
        } | "Pending: \(.pending) | Running: \(.running) | Done: \(.done) | Failed: \(.failed) | Total: \(.total)"' "$QUEUE_FILE"
    else
        # Specific task
        jq ".tasks[] | select(.id | startswith(\"$id\"))" "$QUEUE_FILE"
    fi
}

cmd_cancel() {
    local id="$1"
    jq_update --arg id "$id" '
        .tasks |= map(if (.id | startswith($id)) and .status == "pending"
            then .status = "cancelled"
            else . end)'
    echo "Cancelled: $id"
}

cmd_retry() {
    local id="$1"
    jq_update --arg id "$id" '
        .tasks |= map(if (.id | startswith($id)) and .status == "failed"
            then .status = "pending" | .error = null
            else . end)'
    echo "Retrying: $id"
}

cmd_clear() {
    local what="${1:---completed}"
    case "$what" in
        --completed) jq_update '.tasks |= map(select(.status != "done"))' ;;
        --failed) jq_update '.tasks |= map(select(.status != "failed"))' ;;
        --all) jq_update '.tasks = []' ;;
    esac
    echo "Cleared: $what"
}

cmd_run() {
    local once=false max="$MAX_PARALLEL"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --once) once=true; shift ;;
            --max) max="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    # Check dependencies and get next task
    get_next_task() {
        jq -r '
            .tasks as $all_tasks |
            $all_tasks
            | map(select(.status == "pending"))
            | map(select(
                .after == null or
                (.after as $dep | any($all_tasks[]; .id == $dep and .status == "done"))
            ))
            | sort_by(.priority)
            | first // empty
            | .id
        ' "$QUEUE_FILE" 2>/dev/null || true
    }

    run_task() {
        local id="$1"
        local task=$(jq ".tasks[] | select(.id == \"$id\")" "$QUEUE_FILE")
        local prompt=$(echo "$task" | jq -r '.prompt')
        local agent=$(echo "$task" | jq -r '.agent')
        local worktree=$(echo "$task" | jq -r '.worktree')
        local mode=$(echo "$task" | jq -r '.mode // "cli"')
        local model=$(echo "$task" | jq -r '.model // "sonnet"')

        # Mark as running
        jq_update --arg id "$id" --argjson started "$(now)" '
            .tasks |= map(if .id == $id then .status = "running" | .started = $started else . end)'

        local output success

        if [[ "$mode" == "api" ]]; then
            # Check if API is available and enabled
            if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
                echo "[$(date +%H:%M:%S)] Skipping (API key not set): $id"
                jq_update --arg id "$id" --arg error "ANTHROPIC_API_KEY not set" '
                    .tasks |= map(if .id == $id then .status = "failed" | .error = $error else . end)'
                return
            fi
            if [[ "${QUEUE_ENABLE_API:-0}" != "1" ]]; then
                echo "[$(date +%H:%M:%S)] Skipping (API not enabled): $id"
                jq_update --arg id "$id" --arg error "API mode not enabled (set QUEUE_ENABLE_API=1)" '
                    .tasks |= map(if .id == $id then .status = "failed" | .error = $error else . end)'
                return
            fi

            echo "[$(date +%H:%M:%S)] Running (API/$model): $id"
            local api_executor="${HOME}/.claude/scripts/queue/api-executor.py"
            local venv_python="${HOME}/.claude/data/venv/bin/python3"
            local result
            if result=$("$venv_python" "$api_executor" "$prompt" --model "$model" 2>&1); then
                success=true
                output=$(echo "$result" | jq -r '.output // ""')
                local tokens=$(echo "$result" | jq -r '"\(.tokens.input)/\(.tokens.output)"')
                echo "[$(date +%H:%M:%S)] Done: $id (tokens: $tokens)"
            else
                success=false
                output=$(echo "$result" | jq -r '.error // "Unknown error"' 2>/dev/null || echo "$result")
            fi
        else
            echo "[$(date +%H:%M:%S)] Running (CLI): $id ($agent)"
            local cmd_args=("claude" "--print")
            [[ "$worktree" == "true" ]] && cmd_args+=("--worktree")
            cmd_args+=("-p" "Using agent: $agent. Task: $prompt")

            if output=$("${cmd_args[@]}" 2>&1); then
                success=true
                echo "[$(date +%H:%M:%S)] Done: $id"
            else
                success=false
            fi
        fi

        if [[ "$success" == "true" ]]; then
            jq_update --arg id "$id" --argjson completed "$(now)" '
                .tasks |= map(if .id == $id then .status = "done" | .completed = $completed else . end)'
        else
            local retries=$(echo "$task" | jq -r '.retries')
            local max_retries=$(echo "$task" | jq -r '.max_retries')

            if [[ $retries -lt $max_retries ]]; then
                jq_update --arg id "$id" --arg error "$output" '
                    .tasks |= map(if .id == $id then .status = "pending" | .retries += 1 | .error = $error else . end)'
                echo "[$(date +%H:%M:%S)] Retry queued: $id (attempt $((retries+2)))"
            else
                jq_update --arg id "$id" --arg error "$output" --argjson completed "$(now)" '
                    .tasks |= map(if .id == $id then .status = "failed" | .error = $error | .completed = $completed else . end)'
                echo "[$(date +%H:%M:%S)] Failed: $id"
            fi
        fi
    }

    # Acquire lock helper
    acquire_queue_lock() {
        local waited=0
        while ! (set -o noclobber; echo $$ > "$LOCK_FILE") 2>/dev/null; do
            if [[ $waited -ge 10 ]]; then
                echo "Warning: Could not acquire queue lock" >&2
                return 1
            fi
            sleep 0.5
            ((waited++))
        done
        trap 'rm -f "$LOCK_FILE"' EXIT
        return 0
    }

    release_queue_lock() {
        rm -f "$LOCK_FILE"
    }

    # Main loop
    while true; do
        local running=$(jq '[.tasks[] | select(.status == "running")] | length' "$QUEUE_FILE")

        if [[ $running -lt $max ]]; then
            # Use lock to prevent race condition
            if acquire_queue_lock; then
                local next=$(get_next_task)
                if [[ -n "$next" ]]; then
                    run_task "$next" &
                    release_queue_lock
                    $once && wait && break
                else
                    release_queue_lock
                    if [[ $running -eq 0 ]]; then
                        echo "Queue empty"
                        break
                    fi
                fi
            fi
        fi

        sleep 2
    done

    wait
}

# Main
case "${1:-}" in
    add) shift; cmd_add "$@" ;;
    list) shift; cmd_list "$@" ;;
    status) shift; cmd_status "$@" ;;
    cancel) shift; cmd_cancel "$@" ;;
    retry) shift; cmd_retry "$@" ;;
    clear) shift; cmd_clear "$@" ;;
    run) shift; cmd_run "$@" ;;
    -h|--help|"") usage ;;
    *) echo "Unknown command: $1" >&2; usage; exit 1 ;;
esac
