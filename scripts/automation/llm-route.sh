#!/usr/bin/env bash
set -euo pipefail
# llm-route.sh - Route tasks to the appropriate LLM CLI
#
# Usage:
#   llm-route.sh "analyze this large log file"     # Auto-detect best LLM
#   llm-route.sh -p gemini "summarize this"        # Force specific provider
#   llm-route.sh --list                            # List available providers
#
# Routing logic:
#   - Large context (>100KB input) → gemini-cli (1M context)
#   - Boilerplate generation → codex-cli (cheaper, fast)
#   - Architecture/security/debugging → claude (best reasoning)
#   - Default → claude

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source library scripts
source ~/.claude/scripts/lib/llm-logging.sh
source ~/.claude/scripts/lib/llm-templates.sh

# Available providers and their CLIs (all in PATH)
declare -A PROVIDERS=(
    [claude]="claude"
    [gemini]="gemini"
    [codex]="codex"
    [copilot]="copilot"
)

usage() {
    sed -n '3,12p' "$0" | sed 's/^#  *//'
    echo ""
    echo "Providers:"
    for p in "${!PROVIDERS[@]}"; do
        cmd="${PROVIDERS[$p]}"
        if command -v "${cmd%% *}" &>/dev/null; then
            echo "  $p: $cmd ✓"
        else
            echo "  $p: $cmd (not installed)"
        fi
    done
    exit 0
}

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

list_providers() {
    echo "Available LLM providers:"
    echo ""
    for p in "${!PROVIDERS[@]}"; do
        cmd="${PROVIDERS[$p]}"
        if command -v "$cmd" &>/dev/null; then
            if check_auth "$p"; then
                echo "  ✓ $p ($cmd) - authenticated"
            else
                echo "  ⚠ $p ($cmd) - not authenticated"
            fi
        else
            echo "  ✗ $p ($cmd) - not installed"
        fi
    done
}

detect_provider() {
    local prompt="$1"
    local input_file="${2:-}"

    # Check input size if file provided
    if [[ -n "$input_file" && -f "$input_file" ]]; then
        local size
        size=$(stat -c%s "$input_file" 2>/dev/null || stat -f%z "$input_file" 2>/dev/null || echo 0)
        if [[ "$size" -gt 102400 ]]; then  # >100KB
            echo "gemini"
            return
        fi
    fi

    # Pattern-based routing (updated per plan Phase 4)
    local prompt_lower="${prompt,,}"

    # Architecture/security/debugging → claude (best reasoning)
    if [[ "$prompt_lower" =~ (architect|security|vulnerab|debug|review|refactor|explain.*why) ]]; then
        echo "claude"
        return
    fi

    # Large context hints → gemini
    if [[ "$prompt_lower" =~ (entire|whole|full|complete) ]] && \
       [[ "$prompt_lower" =~ (codebase|project|repository|file) ]]; then
        echo "gemini"
        return
    fi

    # Boilerplate/generation patterns → codex
    if [[ "$prompt_lower" =~ (generate|scaffold|crud|template|boilerplate) ]] && \
       [[ "$prompt_lower" =~ (endpoint|api|model|schema|component) ]]; then
        echo "codex"
        return
    fi

    # Shell commands → copilot
    if [[ "$prompt_lower" =~ (command|terminal|shell|bash|cli) ]] || \
       [[ "$prompt_lower" =~ (explain.*command|what.*does.*command) ]]; then
        echo "copilot"
        return
    fi

    # Default
    echo "claude"
}

invoke_provider() {
    local provider="$1"
    shift
    local prompt="$*"

    # Enhance prompt with provider-specific instructions
    local enhanced_prompt
    enhanced_prompt=$(enhance_prompt "$provider" "" "$prompt")

    # Start timing
    local start_time
    start_time=$(date +%s%3N)

    # Execute based on provider
    local exit_code=0
    case "$provider" in
        claude)
            echo "→ Routing to Claude..." >&2
            claude -p "$enhanced_prompt" || exit_code=$?
            ;;
        gemini)
            echo "→ Routing to Gemini..." >&2
            gemini "$enhanced_prompt" --output-format json || exit_code=$?
            ;;
        codex)
            echo "→ Routing to Codex..." >&2
            codex exec --quiet --json "$enhanced_prompt" || exit_code=$?
            ;;
        copilot)
            echo "→ Routing to GitHub Copilot..." >&2
            copilot "$enhanced_prompt" --allow-all-tools || exit_code=$?
            ;;
        *)
            echo "Unknown provider: $provider" >&2
            exit 1
            ;;
    esac

    # Calculate latency
    local end_time
    end_time=$(date +%s%3N)
    local latency=$((end_time - start_time))

    # Log result
    if [[ $exit_code -eq 0 ]]; then
        log_success "$provider" "$prompt" "invocation_success" "$latency"
    else
        log_failure "$provider" "$prompt" "invocation_failed" "$latency"
    fi

    return $exit_code
}

# Parse arguments
PROVIDER=""
INPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--provider) PROVIDER="$2"; shift 2 ;;
        -f|--file) INPUT_FILE="$2"; shift 2 ;;
        -l|--list) list_providers; exit 0 ;;
        -h|--help) usage ;;
        *) break ;;
    esac
done

PROMPT="$*"

if [[ -z "$PROMPT" && -z "$INPUT_FILE" ]]; then
    usage
fi

# Auto-detect provider if not specified
if [[ -z "$PROVIDER" ]]; then
    PROVIDER=$(detect_provider "$PROMPT" "$INPUT_FILE")
    echo "Auto-detected provider: $PROVIDER" >&2
    log_attempt "$PROVIDER" "$PROMPT" "auto_detected"
else
    log_attempt "$PROVIDER" "$PROMPT" "user_specified"
fi

# Check if provider is available
cmd="${PROVIDERS[$PROVIDER]:-}"
if [[ -z "$cmd" ]]; then
    echo "Unknown provider: $PROVIDER" >&2
    echo "Use --list to see available providers" >&2
    exit 1
fi

if ! command -v "$cmd" &>/dev/null; then
    echo "Provider '$PROVIDER' CLI not installed: $cmd" >&2
    exit 1
fi

# Check authentication
if ! check_auth "$PROVIDER"; then
    echo "Warning: Provider '$PROVIDER' is not authenticated" >&2
    echo "This may cause the request to fail" >&2
fi

# Invoke the provider
if [[ -n "$INPUT_FILE" ]]; then
    # Read file content and append to prompt
    file_content=$(<"$INPUT_FILE")
    invoke_provider "$PROVIDER" "$PROMPT" "$file_content"
elif [[ ! -t 0 ]]; then
    # Read from stdin
    stdin_content=$(cat)
    invoke_provider "$PROVIDER" "$PROMPT" "$stdin_content"
else
    invoke_provider "$PROVIDER" "$PROMPT"
fi
