#!/usr/bin/env bash
# Queue Runner - Background daemon for task queue
# Usage: queue-runner.sh [start|stop|status]

set -euo pipefail

PID_FILE="${HOME}/.claude/data/queue-runner.pid"
LOG_FILE="${HOME}/.claude/data/queue-runner.log"
QUEUE_SCRIPT="${HOME}/.claude/scripts/queue/task-queue.sh"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
MAX_PARALLEL="${MAX_PARALLEL:-3}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

is_running() {
    [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_start() {
    if is_running; then
        echo "Queue runner already running (PID: $(cat "$PID_FILE"))"
        exit 0
    fi

    echo "Starting queue runner..."

    # Daemonize
    (
        trap 'rm -f "$PID_FILE"; log "Stopped"; exit 0' SIGTERM SIGINT

        echo $$ > "$PID_FILE"
        log "Started (PID: $$, MAX_PARALLEL: $MAX_PARALLEL)"

        while true; do
            # Check for pending tasks
            pending=$("$QUEUE_SCRIPT" list --status pending --json | jq 'length')
            running=$("$QUEUE_SCRIPT" list --status running --json | jq 'length')

            if [[ $pending -gt 0 ]] && [[ $running -lt $MAX_PARALLEL ]]; then
                log "Processing queue (pending: $pending, running: $running)"
                "$QUEUE_SCRIPT" run --once >> "$LOG_FILE" 2>&1 &
            fi

            sleep "$POLL_INTERVAL"
        done
    ) &

    disown
    sleep 1

    if is_running; then
        echo "Queue runner started (PID: $(cat "$PID_FILE"))"
        echo "Log: $LOG_FILE"
    else
        echo "Failed to start queue runner" >&2
        exit 1
    fi
}

cmd_stop() {
    if ! is_running; then
        echo "Queue runner not running"
        rm -f "$PID_FILE"
        exit 0
    fi

    local pid=$(cat "$PID_FILE")
    echo "Stopping queue runner (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait for graceful shutdown
    for i in {1..10}; do
        is_running || break
        sleep 1
    done

    if is_running; then
        echo "Force killing..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "Stopped"
}

cmd_status() {
    if is_running; then
        echo "Queue runner: running (PID: $(cat "$PID_FILE"))"
        "$QUEUE_SCRIPT" status
    else
        echo "Queue runner: stopped"
        rm -f "$PID_FILE" 2>/dev/null || true
    fi
}

cmd_logs() {
    local lines="${1:-50}"
    if [[ -f "$LOG_FILE" ]]; then
        tail -n "$lines" "$LOG_FILE"
    else
        echo "No logs found"
    fi
}

case "${1:-status}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    logs) shift; cmd_logs "$@" ;;
    restart) cmd_stop; sleep 1; cmd_start ;;
    *)
        echo "Usage: queue-runner.sh [start|stop|status|logs|restart]"
        exit 1
        ;;
esac
