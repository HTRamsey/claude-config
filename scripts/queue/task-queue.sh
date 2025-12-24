#!/usr/bin/env bash
# Task Queue - Lightweight task queue for Claude Code agents
# Usage: task-queue.sh <command> [args]

SCRIPT_VERSION="1.0.0"

set -euo pipefail

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
    jq "$1" "$QUEUE_FILE" > "$tmp" && mv "$tmp" "$QUEUE_FILE"
}

usage() {
    cat <<EOF
Task Queue - Manage Claude Code agent tasks

Usage: task-queue.sh <command> [args]

Commands:
  add <prompt> [--agent TYPE] [--after ID] [--priority N] [--worktree]
      Add a task to the queue

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
  task-queue.sh add "Review auth module" --agent security-reviewer
  task-queue.sh add "Generate tests" --after abc123 --agent test-generator
  task-queue.sh run --max 3
  task-queue.sh list --status running
EOF
}

cmd_add() {
    local prompt="" agent="Explore" after="" priority=5 worktree=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent) agent="$2"; shift 2 ;;
            --after) after="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --worktree) worktree=true; shift ;;
            --*) echo "Unknown option: $1" >&2; exit 1 ;;
            *) prompt="$1"; shift ;;
        esac
    done

    [[ -z "$prompt" ]] && { echo "Error: prompt required" >&2; exit 1; }

    local id=$(uuid)
    local task=$(jq -n \
        --arg id "$id" \
        --arg prompt "$prompt" \
        --arg agent "$agent" \
        --arg after "$after" \
        --argjson priority "$priority" \
        --argjson worktree "$worktree" \
        --argjson created "$(now)" \
        '{
            id: $id,
            prompt: $prompt,
            agent: $agent,
            after: (if $after == "" then null else $after end),
            priority: $priority,
            worktree: $worktree,
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

        # Mark as running
        jq_update --arg id "$id" --argjson started "$(now)" '
            .tasks |= map(if .id == $id then .status = "running" | .started = $started else . end)'

        echo "[$(date +%H:%M:%S)] Running: $id ($agent)"

        # Build command as array (safe - no shell injection possible)
        local cmd_args=("claude" "--print")
        [[ "$worktree" == "true" ]] && cmd_args+=("--worktree")
        cmd_args+=("-p" "Using agent: $agent. Task: $prompt")

        # Execute using array expansion (no eval needed)
        local output
        if output=$("${cmd_args[@]}" 2>&1); then
            jq_update --arg id "$id" --argjson completed "$(now)" '
                .tasks |= map(if .id == $id then .status = "done" | .completed = $completed else . end)'
            echo "[$(date +%H:%M:%S)] Done: $id"
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
