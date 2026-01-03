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

# Source LLM library scripts
source ~/.claude/scripts/lib/llm-logging.sh
source ~/.claude/scripts/lib/llm-templates.sh
source ~/.claude/scripts/lib/llm-response.sh

# Provider CLI commands for non-interactive mode (all in PATH)
declare -A PROVIDERS=(
    [claude]="claude"
    [gemini]="gemini"
    [codex]="codex"
    [copilot]="copilot"
)

# Fallback chain: Best-fit → Claude → Gemini → Codex → Copilot
FALLBACK_ORDER=(claude gemini codex copilot)

# Check authentication status for a provider
check_auth() {
    local provider="$1"
    case "$provider" in
        gemini)
            [[ -n "${GEMINI_API_KEY:-}" ]] || [[ -n "${GOOGLE_API_KEY:-}" ]] || [[ -f ~/.gemini/.env ]]
            ;;
        codex)
            [[ -n "${OPENAI_API_KEY:-}" ]]
            ;;
        copilot)
            [[ -n "${GH_TOKEN:-}" ]] || [[ -n "${GITHUB_TOKEN:-}" ]] || gh auth status &>/dev/null 2>&1
            ;;
        claude)
            return 0  # Always available
            ;;
        *)
            return 1
            ;;
    esac
}

# Detect provider binary
detect_provider_binary() {
    local provider="$1"
    command -v "$provider" 2>/dev/null
}


# ARG_MAX threshold (use temp file for prompts > 100KB to avoid "argument list too long")
ARG_MAX_THRESHOLD=102400

# Write large content to temp file, return path (or empty if small enough for args)
prepare_large_content() {
    local content="$1"
    local size=${#content}

    if [[ $size -gt $ARG_MAX_THRESHOLD ]]; then
        local tmpfile
        tmpfile=$(mktemp /tmp/llm-prompt.XXXXXX)
        echo "$content" > "$tmpfile"
        echo "$tmpfile"
    fi
}

# Cleanup temp file if created
cleanup_temp() {
    local tmpfile="$1"
    [[ -n "$tmpfile" && -f "$tmpfile" ]] && rm -f "$tmpfile"
}

# Individual provider invocations
invoke_gemini() {
    local prompt="$1"
    local input="${2:-}"
    local timeout="${3:-120}"

    # Enhance prompt with provider-specific template
    local enhanced_prompt
    enhanced_prompt=$(enhance_prompt gemini "" "$prompt")

    # Handle large prompts via temp file
    local tmpfile
    tmpfile=$(prepare_large_content "$enhanced_prompt")

    local cmd=(gemini --output-format json)
    [[ -n "${GEMINI_MODEL:-}" ]] && cmd+=(-m "$GEMINI_MODEL")

    local result
    if [[ -n "$tmpfile" ]]; then
        # Large prompt: use stdin
        result=$(cat "$tmpfile" | timeout "$timeout" "${cmd[@]}")
        cleanup_temp "$tmpfile"
    elif [[ -n "$input" ]]; then
        result=$(echo "$input" | timeout "$timeout" "${cmd[@]}" "$enhanced_prompt")
    else
        result=$(timeout "$timeout" "${cmd[@]}" "$enhanced_prompt")
    fi

    # Parse and normalize response
    echo "$result" | parse_response gemini
}

invoke_codex() {
    local prompt="$1"
    local input="${2:-}"
    local timeout="${3:-120}"

    # Enhance prompt with provider-specific template
    local enhanced_prompt
    enhanced_prompt=$(enhance_prompt codex "" "$prompt")

    # Handle large prompts via temp file
    local tmpfile
    tmpfile=$(prepare_large_content "$enhanced_prompt")

    local cmd=(codex exec --json --full-auto -s workspace-write)
    [[ -n "${CODEX_MODEL:-}" ]] && cmd+=(-m "$CODEX_MODEL")

    local result
    if [[ -n "$tmpfile" ]]; then
        # Large prompt: use stdin (- tells codex to read from stdin)
        result=$(cat "$tmpfile" | timeout "$timeout" "${cmd[@]}" -)
        cleanup_temp "$tmpfile"
    elif [[ -n "$input" ]]; then
        result=$(echo "$input" | timeout "$timeout" "${cmd[@]}" -)
    else
        result=$(timeout "$timeout" "${cmd[@]}" "$enhanced_prompt")
    fi

    # Parse and normalize response
    echo "$result" | parse_response codex
}

invoke_copilot() {
    local prompt="$1"
    local input="${2:-}"
    local timeout="${3:-120}"

    # Enhance prompt with provider-specific template
    local enhanced_prompt
    enhanced_prompt=$(enhance_prompt copilot "" "$prompt")

    if [[ -n "$input" ]]; then
        # Copilot doesn't support stdin piping, prepend to prompt
        enhanced_prompt="$input

$enhanced_prompt"
    fi

    # Handle large prompts via temp file
    local tmpfile
    tmpfile=$(prepare_large_content "$enhanced_prompt")

    local result
    if [[ -n "$tmpfile" ]]; then
        # Large prompt: read from file, pass via -p
        # Copilot -p has size limits, so we truncate with warning
        local content
        content=$(head -c 50000 "$tmpfile")
        if [[ $(wc -c < "$tmpfile") -gt 50000 ]]; then
            echo "[WARN] Prompt truncated to 50KB for Copilot" >&2
        fi
        result=$(timeout "$timeout" copilot -p "$content" --allow-all-tools 2>&1)
        cleanup_temp "$tmpfile"
    else
        # Use -p for non-interactive prompt mode
        # Capture both stdout and stderr, usage stats go to stderr
        result=$(timeout "$timeout" copilot -p "$enhanced_prompt" --allow-all-tools 2>&1)
    fi

    # Parse and normalize response (strips usage stats)
    echo "$result" | parse_response copilot
}

invoke_claude() {
    local prompt="$1"
    local input="${2:-}"
    local timeout="${3:-120}"

    # Enhance prompt with provider-specific template
    local enhanced_prompt
    enhanced_prompt=$(enhance_prompt claude "" "$prompt")

    # Handle large prompts via temp file
    local tmpfile
    tmpfile=$(prepare_large_content "$enhanced_prompt")

    # Claude invocation - typically we're already in Claude, so this is for delegation
    local result
    if [[ -n "$tmpfile" ]]; then
        # Large prompt: use stdin with -p -
        result=$(cat "$tmpfile" | timeout "$timeout" claude -p - --output-format text)
        cleanup_temp "$tmpfile"
    elif [[ -n "$input" ]]; then
        result=$(echo "$input" | timeout "$timeout" claude -p "$enhanced_prompt" --output-format text)
    else
        result=$(timeout "$timeout" claude -p "$enhanced_prompt" --output-format text)
    fi

    # Parse and normalize response
    echo "$result" | parse_response claude
}

invoke_provider() {
    local provider="$1"
    shift
    case "$provider" in
        gemini)  invoke_gemini "$@" ;;
        codex)   invoke_codex "$@" ;;
        copilot) invoke_copilot "$@" ;;
        claude)  invoke_claude "$@" ;;
    esac
}

# Invoke with fallback chain
invoke_with_fallback() {
    local prompt="$1"
    local input="${2:-}"
    local timeout="${3:-120}"
    local preferred="${4:-}"

    # Build provider list: preferred first, then fallback order
    local providers=()
    [[ -n "$preferred" ]] && providers+=("$preferred")
    for p in "${FALLBACK_ORDER[@]}"; do
        [[ "$p" != "$preferred" ]] && providers+=("$p")
    done

    # Try each provider
    for provider in "${providers[@]}"; do
        if detect_provider_binary "$provider" &>/dev/null && check_auth "$provider"; then
            log_routing "$provider" "$prompt" "attempting"
            if result=$(invoke_provider "$provider" "$prompt" "$input" "$timeout" 2>&1); then
                log_routing "$provider" "$prompt" "success"
                echo "$result"
                return 0
            else
                log_routing "$provider" "$prompt" "failed: $result"
            fi
        fi
    done

    log_routing "none" "$prompt" "all providers failed"
    return 1
}

usage() {
    cat <<'EOF'
llm-delegate.sh - Delegate tasks to other LLMs with automatic fallback

Usage:
  llm-delegate.sh gemini "summarize this large file"
  llm-delegate.sh codex "generate CRUD endpoints for User model"
  cat large.log | llm-delegate.sh gemini "summarize this"
EOF
    echo ""
    echo "Options:"
    echo "  -t, --timeout SEC    Timeout in seconds (default: 120)"
    echo "  -f, --fallback       Enable fallback chain (default: enabled)"
    echo "  -i, --interactive    Use tmux-based interactive mode (legacy)"
    echo "  -k, --keep           Keep tmux session after completion (interactive mode only)"
    echo "  -h, --help           Show this help"
    echo ""
    echo "Providers:"
    echo "  gemini    Uses positional prompt with --output-format json"
    echo "  codex     Uses 'exec --full-auto' with workspace-write sandbox"
    echo "  copilot   Uses standalone binary with --allow-all-tools"
    echo "  claude    Uses -p with --output-format text"
    echo ""
    echo "Fallback chain (if preferred fails):"
    echo "  Best-fit → Claude → Gemini → Codex → Copilot"
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

# Non-interactive delegation with fallback (default)
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

    # Use fallback chain if enabled
    if [[ "${USE_FALLBACK:-true}" == "true" ]]; then
        invoke_with_fallback "$prompt" "$stdin_content" "$TIMEOUT" "$provider"
    else
        # Direct invocation (no fallback)
        if ! command -v "$cli" &>/dev/null; then
            echo "CLI not found: $cli" >&2
            return 1
        fi

        if ! check_auth "$provider"; then
            echo "Provider '$provider' is not authenticated" >&2
            return 1
        fi

        invoke_provider "$provider" "$prompt" "$stdin_content" "$TIMEOUT"
    fi
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
USE_FALLBACK="true"

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--timeout) TIMEOUT="$2"; shift 2 ;;
        -f|--fallback) USE_FALLBACK="true"; shift ;;
        --no-fallback) USE_FALLBACK="false"; shift ;;
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
