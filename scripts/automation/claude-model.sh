#!/usr/bin/env bash
# claude-model.sh - Smart model selection for Claude Code
# Automatically selects the most cost-effective model based on task type
#
# Usage:
#   claude-model.sh <task-type> "prompt"
#   claude-model.sh auto "prompt"        # Auto-detect complexity
#   claude-model.sh simple "quick question"
#   claude-model.sh moderate "implement feature"
#   claude-model.sh complex "architect system"
#
# Task types:
#   simple   -> Haiku    (80% cheaper): Quick questions, simple lookups, formatting
#   moderate -> Sonnet   (default): Feature implementation, debugging, code review
#   complex  -> Opus     (most capable): Architecture, complex reasoning, planning
#   auto     -> Auto-detect based on prompt analysis

set -e

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Model mappings
MODEL_HAIKU="claude-haiku-4-5-latest"
MODEL_SONNET="claude-sonnet-4-5-latest"
MODEL_OPUS="claude-opus-4-5-latest"

log_info() { echo -e "${GREEN}[MODEL]${NC} $1" >&2; }
log_model() { echo -e "${BLUE}[MODEL]${NC} Selected: $1" >&2; }

# Keywords for complexity detection
# CONFIGURATION: Uses Haiku only for simple lookups, Opus for everything else
SIMPLE_KEYWORDS="what is|what does|how do i|explain this error|show me|format this|convert|typo|syntax error"

detect_complexity() {
    local prompt="$1"
    local prompt_lower=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')
    local word_count=$(echo "$prompt" | wc -w)

    # Only use Haiku for very simple, short queries
    if echo "$prompt_lower" | grep -qiE "$SIMPLE_KEYWORDS"; then
        if [[ $word_count -lt 10 ]]; then
            echo "simple"
            return
        fi
    fi

    # Default to Opus for everything else (heavily favored)
    echo "complex"
}

select_model() {
    local task_type="$1"

    case "$task_type" in
        simple|quick|haiku)
            echo "$MODEL_HAIKU"
            ;;
        moderate|default|sonnet)
            echo "$MODEL_SONNET"
            ;;
        complex|hard|opus)
            echo "$MODEL_OPUS"
            ;;
        *)
            echo "$MODEL_SONNET"
            ;;
    esac
}

get_cost_estimate() {
    local model="$1"
    case "$model" in
        *haiku*)
            echo "~\$0.01-0.05"
            ;;
        *sonnet*)
            echo "~\$0.05-0.30"
            ;;
        *opus*)
            echo "~\$0.30-2.00"
            ;;
    esac
}

# Parse arguments
TASK_TYPE="${1:-auto}"
shift || true

# Get prompt
if [[ "$1" == "-f" ]]; then
    PROMPT=$(cat "$2")
elif [[ "$1" == "-" ]]; then
    PROMPT=$(cat)
elif [[ -n "$1" ]]; then
    PROMPT="$*"
else
    echo "Usage: claude-model.sh <task-type|auto> \"prompt\""
    echo ""
    echo "Task types:"
    echo "  simple   -> Haiku (80% cheaper)"
    echo "  moderate -> Sonnet (default)"
    echo "  complex  -> Opus (most capable)"
    echo "  auto     -> Auto-detect"
    echo ""
    echo "Examples:"
    echo "  claude-model.sh simple \"What does this error mean?\""
    echo "  claude-model.sh auto \"Refactor the authentication system\""
    echo "  claude-model.sh complex \"Design a microservices architecture\""
    exit 1
fi

# Auto-detect if needed
if [[ "$TASK_TYPE" == "auto" ]]; then
    TASK_TYPE=$(detect_complexity "$PROMPT")
    log_info "Auto-detected complexity: $TASK_TYPE"
fi

# Select model
MODEL=$(select_model "$TASK_TYPE")
COST=$(get_cost_estimate "$MODEL")

log_model "$MODEL ($TASK_TYPE task, est. $COST)"

# Check for dry run
if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "claude --model $MODEL -p \"$PROMPT\""
    exit 0
fi

# Run Claude with selected model
exec claude --model "$MODEL" -p "$PROMPT"
