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

# Available providers and their CLIs
declare -A PROVIDERS=(
    [claude]="claude"
    [gemini]="gemini"
    [codex]="codex"
    [copilot]="gh copilot suggest"
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

list_providers() {
    echo "Available LLM providers:"
    echo ""
    for p in "${!PROVIDERS[@]}"; do
        cmd="${PROVIDERS[$p]}"
        if command -v "${cmd%% *}" &>/dev/null; then
            echo "  ✓ $p ($cmd)"
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

    # Pattern-based routing
    local prompt_lower="${prompt,,}"

    # Boilerplate patterns → codex
    if [[ "$prompt_lower" =~ (generate|create|scaffold|boilerplate|crud|template) ]] && \
       [[ "$prompt_lower" =~ (endpoint|api|model|schema|component|class) ]]; then
        echo "codex"
        return
    fi

    # Architecture/security/debugging → claude
    if [[ "$prompt_lower" =~ (architect|security|vulnerability|debug|review|refactor|explain|analyze) ]]; then
        echo "claude"
        return
    fi

    # Large context hints → gemini
    if [[ "$prompt_lower" =~ (entire|whole|full|all\ of|complete) ]] && \
       [[ "$prompt_lower" =~ (codebase|project|repository|file) ]]; then
        echo "gemini"
        return
    fi

    # Default
    echo "claude"
}

invoke_provider() {
    local provider="$1"
    shift
    local prompt="$*"

    case "$provider" in
        claude)
            echo "→ Routing to Claude..." >&2
            claude "$prompt"
            ;;
        gemini)
            echo "→ Routing to Gemini..." >&2
            gemini "$prompt"
            ;;
        codex)
            echo "→ Routing to Codex..." >&2
            codex "$prompt"
            ;;
        copilot)
            echo "→ Routing to GitHub Copilot..." >&2
            gh copilot suggest "$prompt"
            ;;
        *)
            echo "Unknown provider: $provider" >&2
            exit 1
            ;;
    esac
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
fi

# Check if provider is available
cmd="${PROVIDERS[$PROVIDER]:-}"
if [[ -z "$cmd" ]]; then
    echo "Unknown provider: $PROVIDER" >&2
    echo "Use --list to see available providers" >&2
    exit 1
fi

if ! command -v "${cmd%% *}" &>/dev/null; then
    echo "Provider '$PROVIDER' CLI not installed: $cmd" >&2
    exit 1
fi

# Invoke the provider
if [[ -n "$INPUT_FILE" ]]; then
    invoke_provider "$PROVIDER" "$PROMPT" < "$INPUT_FILE"
else
    invoke_provider "$PROVIDER" "$PROMPT"
fi
