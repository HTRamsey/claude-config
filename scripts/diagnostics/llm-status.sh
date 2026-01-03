#!/usr/bin/env bash
# Check status of all LLM providers

set -euo pipefail

echo "=== LLM Provider Status ==="
echo ""

check_provider() {
    local name="$1"
    local auth_check="$2"

    printf "%-10s " "$name:"

    local binary
    if ! binary=$(command -v "$name" 2>/dev/null); then
        echo "✗ NOT INSTALLED"
        return
    fi

    # Get version (provider-specific handling)
    local version=""
    case "$name" in
        gemini)
            version=$(gemini --version 2>&1 | grep -oP 'v?\d+\.\d+\.\d+' | head -1 || echo "unknown")
            ;;
        codex)
            version=$(codex --version 2>&1 | grep -oP 'v?\d+\.\d+\.\d+' | head -1 || echo "unknown")
            ;;
        copilot)
            version=$(copilot --version 2>&1 | grep -oP 'v?\d+\.\d+\.\d+' | head -1 || echo "unknown")
            ;;
        claude)
            version=$(claude --version 2>&1 | grep -oP 'v?\d+\.\d+\.\d+' | head -1 || echo "installed")
            ;;
        *)
            version=$("$binary" --version 2>&1 | head -1 || echo "unknown")
            ;;
    esac

    # Check authentication
    if eval "$auth_check" 2>/dev/null; then
        echo "✓ v$version (authenticated)"
    else
        echo "⚠ v$version (not authenticated)"
    fi
}

# Check all providers
check_provider "gemini" '[[ -n "${GEMINI_API_KEY:-}" ]] || [[ -n "${GOOGLE_API_KEY:-}" ]] || [[ -f ~/.gemini/.env ]]'
check_provider "codex" '[[ -n "${OPENAI_API_KEY:-}" ]]'
check_provider "copilot" '[[ -n "${GH_TOKEN:-}" ]] || [[ -n "${GITHUB_TOKEN:-}" ]]'
check_provider "claude" 'true'

echo ""
echo "=== Environment Variables ==="

# Helper to show env var status
show_env() {
    local var="$1"
    local value="${!var:-}"
    if [[ -n "$value" ]]; then
        echo "$var: set"
    else
        echo "$var: not set"
    fi
}

show_env "GEMINI_API_KEY"
show_env "GOOGLE_API_KEY"
show_env "OPENAI_API_KEY"
show_env "GH_TOKEN"
show_env "GITHUB_TOKEN"

echo ""
echo "=== Recent Routing (last 5) ==="
ROUTING_LOG="$HOME/.claude/data/logs/llm-routing.jsonl"

if [[ -f "$ROUTING_LOG" ]]; then
    if command -v jq &>/dev/null; then
        tail -5 "$ROUTING_LOG" | jq -r '"[\(.timestamp)] \(.provider): \(.status) (\(.reason // "no reason"))"'
    else
        tail -5 "$ROUTING_LOG"
    fi
else
    echo "No routing history yet"
    echo "(Log file: $ROUTING_LOG)"
fi
