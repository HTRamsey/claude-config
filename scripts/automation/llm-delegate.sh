#!/usr/bin/env bash
set -euo pipefail
# llm-delegate.sh - Delegate tasks to other LLMs (non-interactive by default)
#
# Usage:
#   llm-delegate.sh gemini "summarize this large file"
#   llm-delegate.sh codex "generate CRUD endpoints for User model"
#   cat large.log | llm-delegate.sh gemini "summarize this"
#
# This script delegates tasks to other LLM CLIs using their non-interactive modes.
# Use -i/--interactive for tmux-based interactive mode (legacy).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="llm-delegate"
TIMEOUT="${LLM_DELEGATE_TIMEOUT:-120}"  # Default 2 min timeout
INTERACTIVE="false"

# Provider CLI commands for non-interactive mode
declare -A PROVIDERS=(
    [claude]="claude"
    [gemini]="gemini"
    [codex]="codex"
)

# Non-interactive command builders
build_command() {
    local provider="$1"
    local prompt="$2"
    local stdin_file="${3:-}"

    case "$provider" in
        claude)
            # Claude: use -p for prompt, --dangerously-skip-permissions for auto-approve
            if [[ -n "$stdin_file" ]]; then
                echo "cat '$stdin_file' | claude --dangerously-skip-permissions -p '$prompt'"
            else
                echo "claude --dangerously-skip-permissions -p '$prompt'"
            fi
            ;;
        gemini)
            # Gemini: use -y for yolo mode (auto-approve), positional prompt
            if [[ -n "$stdin_file" ]]; then
                echo "cat '$stdin_file' | gemini -y '$prompt'"
            else
                echo "gemini -y '$prompt'"
            fi
            ;;
        codex)
            # Codex: use exec subcommand for non-interactive
            if [[ -n "$stdin_file" ]]; then
                echo "cat '$stdin_file' | codex exec '$prompt'"
            else
                echo "codex exec '$prompt'"
            fi
            ;;
        *)
            echo ""
            ;;
    esac
}

usage() {
    cat <<'EOF'
llm-delegate.sh - Delegate tasks to other LLMs (non-interactive by default)

Usage:
  llm-delegate.sh gemini "summarize this large file"
  llm-delegate.sh codex "generate CRUD endpoints for User model"
  cat large.log | llm-delegate.sh gemini "summarize this"
EOF
    echo ""
    echo "Options:"
    echo "  -t, --timeout SEC    Timeout in seconds (default: 120)"
    echo "  -i, --interactive    Use tmux-based interactive mode (legacy)"
    echo "  -k, --keep           Keep tmux session after completion (interactive mode only)"
    echo "  -h, --help           Show this help"
    echo ""
    echo "Providers:"
    echo "  gemini    Uses -y (yolo mode) for auto-approval"
    echo "  codex     Uses 'exec' subcommand for non-interactive"
    echo "  claude    Uses --dangerously-skip-permissions -p"
    echo ""
    echo "Environment:"
    echo "  LLM_DELEGATE_TIMEOUT  Default timeout in seconds"
    exit 0
}

cleanup() {
    local pane="$1"
    if [[ "$KEEP_SESSION" != "true" ]]; then
        tmux kill-pane -t "$pane" 2>/dev/null || true
    fi
}

wait_for_prompt() {
    local pane="$1"
    local provider="$2"
    local max_wait=30
    local waited=0

    # Wait for CLI to be ready (prompt appears)
    while [[ $waited -lt $max_wait ]]; do
        local content
        content=$(tmux capture-pane -t "$pane" -p 2>/dev/null || echo "")

        # Check for various prompt indicators
        case "$provider" in
            claude)
                [[ "$content" =~ (\$|>|❯) ]] && return 0
                ;;
            gemini)
                [[ "$content" =~ (>|\?) ]] && return 0
                ;;
            codex)
                [[ "$content" =~ (>|\$) ]] && return 0
                ;;
        esac

        sleep 0.5
        waited=$((waited + 1))
    done

    echo "Timeout waiting for $provider CLI to start" >&2
    return 1
}

wait_for_response() {
    local pane="$1"
    local timeout="$2"
    local start_lines="$3"
    local waited=0
    local stable_count=0
    local last_lines=0

    while [[ $waited -lt $timeout ]]; do
        local content
        content=$(tmux capture-pane -t "$pane" -p -S - 2>/dev/null || echo "")
        local current_lines
        current_lines=$(echo "$content" | wc -l)

        # Response is complete when output stabilizes
        if [[ $current_lines -eq $last_lines && $current_lines -gt $start_lines ]]; then
            stable_count=$((stable_count + 1))
            if [[ $stable_count -ge 4 ]]; then  # Stable for 2 seconds
                return 0
            fi
        else
            stable_count=0
        fi

        last_lines=$current_lines
        sleep 0.5
        waited=$((waited + 1))
    done

    echo "Timeout waiting for response" >&2
    return 1
}

capture_response() {
    local pane="$1"
    local prompt="$2"

    # Capture full pane content
    local content
    content=$(tmux capture-pane -t "$pane" -p -S - 2>/dev/null || echo "")

    # Remove the prompt echo and extract just the response
    # This is heuristic - different CLIs format differently
    echo "$content" | tail -n +3 | head -n -1
}

# Non-interactive delegation (default)
delegate_noninteractive() {
    local provider="$1"
    local prompt="$2"
    local stdin_content="${3:-}"

    # Check if CLI exists
    local cli="${PROVIDERS[$provider]:-}"
    if [[ -z "$cli" ]]; then
        echo "Unknown provider: $provider" >&2
        echo "Available: ${!PROVIDERS[*]}" >&2
        return 1
    fi

    if ! command -v "$cli" &>/dev/null; then
        echo "CLI not found: $cli" >&2
        return 1
    fi

    # Handle stdin content via temp file if provided
    local stdin_file=""
    if [[ -n "$stdin_content" ]]; then
        stdin_file=$(mktemp)
        echo "$stdin_content" > "$stdin_file"
        trap "rm -f '$stdin_file'" EXIT
    fi

    # Build and execute command
    case "$provider" in
        claude)
            if [[ -n "$stdin_file" ]]; then
                cat "$stdin_file" | timeout "$TIMEOUT" claude --dangerously-skip-permissions -p "$prompt" 2>&1
            else
                timeout "$TIMEOUT" claude --dangerously-skip-permissions -p "$prompt" 2>&1
            fi
            ;;
        gemini)
            if [[ -n "$stdin_file" ]]; then
                cat "$stdin_file" | timeout "$TIMEOUT" gemini -y "$prompt" 2>&1
            else
                timeout "$TIMEOUT" gemini -y "$prompt" 2>&1
            fi
            ;;
        codex)
            if [[ -n "$stdin_file" ]]; then
                cat "$stdin_file" | timeout "$TIMEOUT" codex exec "$prompt" 2>&1
            else
                timeout "$TIMEOUT" codex exec "$prompt" 2>&1
            fi
            ;;
        *)
            echo "Unknown provider: $provider" >&2
            return 1
            ;;
    esac

    local exit_code=$?
    [[ -n "$stdin_file" ]] && rm -f "$stdin_file"
    return $exit_code
}

# Interactive delegation via tmux (legacy, use -i flag)
delegate_interactive() {
    local provider="$1"
    local prompt="$2"
    local stdin_content="${3:-}"

    local cli="${PROVIDERS[$provider]:-}"
    if [[ -z "$cli" ]]; then
        echo "Unknown provider: $provider" >&2
        echo "Available: ${!PROVIDERS[*]}" >&2
        return 1
    fi

    # Check if CLI exists
    if ! command -v "$cli" &>/dev/null; then
        echo "CLI not found: $cli" >&2
        return 1
    fi

    # Create tmux session if needed
    if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50
    fi

    # Create new pane for this request
    local pane
    pane=$(tmux new-window -t "$SESSION_NAME" -P -F "#{pane_id}")
    trap "cleanup '$pane'" EXIT

    # Prepare the full prompt
    local full_prompt="$prompt"
    if [[ -n "$stdin_content" ]]; then
        full_prompt="$stdin_content

$prompt"
    fi

    # Start the CLI
    tmux send-keys -t "$pane" "$cli" Enter
    sleep 1

    # Get starting line count
    local start_lines
    start_lines=$(tmux capture-pane -t "$pane" -p | wc -l)

    # Send the prompt (escape special characters)
    local escaped_prompt
    escaped_prompt=$(printf '%s' "$full_prompt" | sed "s/'/'\\\\''/g")
    tmux send-keys -t "$pane" "$escaped_prompt" Enter

    # Wait for response
    if ! wait_for_response "$pane" "$TIMEOUT" "$start_lines"; then
        echo "Response timed out after ${TIMEOUT}s" >&2
        tmux capture-pane -t "$pane" -p -S -
        return 1
    fi

    # Capture and output response
    capture_response "$pane" "$prompt"
}

# Parse arguments
KEEP_SESSION="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--timeout) TIMEOUT="$2"; shift 2 ;;
        -i|--interactive) INTERACTIVE="true"; shift ;;
        -k|--keep) KEEP_SESSION="true"; shift ;;
        -h|--help) usage ;;
        *) break ;;
    esac
done

if [[ $# -lt 2 ]]; then
    usage
fi

PROVIDER="$1"
shift
PROMPT="$*"

# Check for stdin
STDIN_CONTENT=""
if [[ ! -t 0 ]]; then
    STDIN_CONTENT=$(cat)
fi

# Run delegation (non-interactive by default)
if [[ "$INTERACTIVE" == "true" ]]; then
    delegate_interactive "$PROVIDER" "$PROMPT" "$STDIN_CONTENT"
else
    delegate_noninteractive "$PROVIDER" "$PROMPT" "$STDIN_CONTENT"
fi
