#!/usr/bin/env bash
# llm-response.sh - Normalize LLM provider responses to plain text
#
# Usage:
#   # As library
#   source ~/.claude/scripts/lib/llm-response.sh
#   gemini "hello" --output-format json | parse_response gemini
#
#   # As CLI
#   echo '{"response":"text"}' | llm-response.sh gemini
#   llm-response.sh -p gemini < response.json
#
# Supported providers: gemini, codex, copilot, claude

LLM_RESPONSE_VERSION="1.0.0"

# Prevent double-sourcing
[[ -n "${LLM_RESPONSE_LOADED:-}" ]] && return 0
LLM_RESPONSE_LOADED=1

# Source common utilities if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/common.sh" ]]; then
    source "$SCRIPT_DIR/common.sh"
else
    # Fallback logging
    log_error() { echo "[ERROR] $*" >&2; }
    log_warn() { echo "[WARN] $*" >&2; }
fi

#
# Parse response from different LLM providers
#
# Args:
#   $1 - Provider name (gemini|codex|copilot|claude)
#   stdin - Response data
#
# Returns:
#   Plain text content on stdout
#
parse_response() {
    local provider="${1:-}"

    if [[ -z "$provider" ]]; then
        log_error "Provider name required"
        return 1
    fi

    # Read entire input
    local input
    input=$(cat)

    if [[ -z "$input" ]]; then
        return 0
    fi

    # Check if jq is available
    if ! command -v jq &>/dev/null; then
        log_warn "jq not found, returning original output"
        echo "$input"
        return 0
    fi

    case "${provider,,}" in
        gemini)
            parse_gemini "$input"
            ;;
        codex)
            parse_codex "$input"
            ;;
        copilot)
            parse_copilot "$input"
            ;;
        claude)
            parse_claude "$input"
            ;;
        *)
            log_error "Unknown provider: $provider"
            echo "$input"
            return 1
            ;;
    esac
}

#
# Parse Gemini response
# Handles: {"candidates":[{"content":{"parts":[{"text":"..."}]}}]}
#      or: {"response":"..."}
#
parse_gemini() {
    local input="$1"
    local text

    # Try complex format first
    text=$(echo "$input" | jq -r '.candidates[0].content.parts[0].text // empty' 2>/dev/null)

    # Try simple format
    if [[ -z "$text" ]]; then
        text=$(echo "$input" | jq -r '.response // empty' 2>/dev/null)
    fi

    # Try direct text field
    if [[ -z "$text" ]]; then
        text=$(echo "$input" | jq -r '.text // empty' 2>/dev/null)
    fi

    # If still no JSON match, return original
    if [[ -z "$text" ]]; then
        echo "$input"
    else
        echo "$text"
    fi
}

#
# Parse Codex response (JSONL stream)
# Handles: {"type":"item.completed","item":{"text":"..."}}
#      or: {"type":"message","content":"..."}
#
parse_codex() {
    local input="$1"
    local accumulated=""

    # Check if it's JSONL (multiple lines, each valid JSON)
    if echo "$input" | head -n1 | jq . &>/dev/null; then
        # Process each line
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue

            local msg_type
            msg_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

            case "$msg_type" in
                item.completed)
                    # New format: {"type":"item.completed","item":{"text":"..."}}
                    local text
                    text=$(echo "$line" | jq -r '.item.text // empty' 2>/dev/null)
                    if [[ -n "$text" ]]; then
                        accumulated+="$text"$'\n'
                    fi
                    ;;
                message)
                    # Legacy format
                    local content
                    content=$(echo "$line" | jq -r '.content // empty' 2>/dev/null)
                    if [[ -n "$content" ]]; then
                        accumulated+="$content"
                    fi
                    ;;
                done|turn.completed)
                    break
                    ;;
            esac
        done <<< "$input"

        if [[ -n "$accumulated" ]]; then
            # Trim trailing newline
            echo "${accumulated%$'\n'}"
        else
            echo "$input"
        fi
    else
        # Not JSONL, try single JSON object
        local text
        text=$(echo "$input" | jq -r '.content // .text // .response // empty' 2>/dev/null)
        if [[ -n "$text" ]]; then
            echo "$text"
        else
            echo "$input"
        fi
    fi
}

#
# Parse Copilot response
# Usually plain text with usage stats header to strip
#
parse_copilot() {
    local input="$1"

    # Try JSON first
    if echo "$input" | jq . &>/dev/null; then
        local text
        text=$(echo "$input" | jq -r '.text // .response // .content // empty' 2>/dev/null)
        if [[ -n "$text" ]]; then
            echo "$text"
            return
        fi
    fi

    # Strip usage stats header (lines starting with: Total, Usage by model, spaces+model names)
    # Keep content after tool execution markers (✓, $, └)
    echo "$input" | sed -E '
        # Remove usage stats block at start
        /^Total usage/d
        /^Total duration/d
        /^Total code changes/d
        /^Usage by model/d
        /^[[:space:]]+(claude|gpt|o1|o3)/d
        # Remove empty lines at start
        /^$/d
    '
}

#
# Parse Claude response
# Can be plain text or JSON
#
parse_claude() {
    local input="$1"

    # Try JSON first
    if echo "$input" | jq . &>/dev/null; then
        # Try common fields
        local text
        text=$(echo "$input" | jq -r '.content[0].text // .text // .response // empty' 2>/dev/null)
        if [[ -n "$text" ]]; then
            echo "$text"
            return
        fi
    fi

    # Return as-is (likely plain text)
    echo "$input"
}

#
# CLI interface
#
main() {
    local provider=""

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -p|--provider)
                provider="$2"
                shift 2
                ;;
            -h|--help)
                cat << EOF
Usage: llm-response.sh [OPTIONS] [PROVIDER]

Normalize LLM provider responses to plain text.

Arguments:
  PROVIDER              Provider name (gemini|codex|copilot|claude)

Options:
  -p, --provider NAME   Provider name (alternative to positional arg)
  -h, --help           Show this help

Examples:
  echo '{"response":"hello"}' | llm-response.sh gemini
  llm-response.sh -p gemini < response.json
  gemini "query" | llm-response.sh gemini

Supported Providers:
  gemini    Google Gemini (JSON formats)
  codex     OpenAI Codex (JSONL stream or JSON)
  copilot   GitHub Copilot (plain text or JSON)
  claude    Anthropic Claude (plain text or JSON)
EOF
                return 0
                ;;
            -*)
                log_error "Unknown option: $1"
                return 1
                ;;
            *)
                provider="$1"
                shift
                ;;
        esac
    done

    if [[ -z "$provider" ]]; then
        log_error "Provider name required"
        echo "Usage: llm-response.sh [OPTIONS] PROVIDER" >&2
        return 1
    fi

    parse_response "$provider"
}

# Only run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
