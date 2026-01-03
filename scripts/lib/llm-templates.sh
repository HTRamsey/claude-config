#!/usr/bin/env bash
# llm-templates.sh - Provider-specific prompt enhancement
# Adapts prompts for different LLM providers based on their strengths

set -euo pipefail

# Detect task type from prompt keywords
detect_task_type() {
    local prompt="$1"
    local lower_prompt
    lower_prompt=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')

    # Summarization
    if [[ "$lower_prompt" =~ (summarize|summary|overview|tldr|condense) ]]; then
        echo "summarization"
        return
    fi

    # Generation
    if [[ "$lower_prompt" =~ (generate|create|scaffold|crud|build|implement|write) ]]; then
        echo "generation"
        return
    fi

    # Explanation
    if [[ "$lower_prompt" =~ (explain|what does|how to|what is|describe|tell me about) ]]; then
        echo "explanation"
        return
    fi

    # Analysis
    if [[ "$lower_prompt" =~ (review|analyze|check|inspect|examine|assess|evaluate) ]]; then
        echo "analysis"
        return
    fi

    # Debugging
    if [[ "$lower_prompt" =~ (debug|fix|error|bug|issue|problem|troubleshoot) ]]; then
        echo "debugging"
        return
    fi

    # Default
    echo "general"
}

# Get template for provider and task type
get_template() {
    local provider="$1"
    local task_type="$2"
    local position="${3:-prefix}"  # prefix or suffix

    case "$provider" in
        gemini)
            case "$task_type" in
                summarization)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Be concise and focus on key findings. Provide a structured summary with clear sections."
                    fi
                    ;;
                analysis)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Identify patterns, anomalies, and key insights. Be systematic and thorough."
                    fi
                    ;;
                *)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Be concise and focus on the most important information."
                    fi
                    ;;
            esac
            ;;

        codex)
            case "$task_type" in
                generation)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Generate production-ready code. Include error handling and input validation. Follow best practices for the language."
                    fi
                    ;;
                *)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Generate production-ready code with proper error handling."
                    fi
                    ;;
            esac
            if [[ "$position" == "suffix" && "$task_type" =~ (generation|general) ]]; then
                echo "Include comprehensive comments and docstrings."
            fi
            ;;

        copilot)
            case "$task_type" in
                explanation)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Explain step by step in a clear and concise manner."
                    fi
                    ;;
                *)
                    if [[ "$position" == "prefix" ]]; then
                        echo "Show the command or solution first, then provide a concise explanation."
                    fi
                    ;;
            esac
            ;;

        claude)
            # Claude doesn't need modification - already optimal
            echo ""
            ;;

        *)
            # Unknown provider - no modification
            echo ""
            ;;
    esac
}

# Enhance prompt with provider-specific instructions
enhance_prompt() {
    local provider="$1"
    local task_type="$2"
    local prompt="$3"

    # Auto-detect task type if not provided
    if [[ -z "$task_type" ]]; then
        task_type=$(detect_task_type "$prompt")
    fi

    # Get prefix and suffix templates
    local prefix=$(get_template "$provider" "$task_type" "prefix")
    local suffix=$(get_template "$provider" "$task_type" "suffix")

    # Build enhanced prompt
    local enhanced=""
    if [[ -n "$prefix" ]]; then
        enhanced="$prefix\n\n"
    fi
    enhanced+="$prompt"
    if [[ -n "$suffix" ]]; then
        enhanced+="\n\n$suffix"
    fi

    echo -e "$enhanced"
}

# Show usage
show_usage() {
    cat <<'EOF'
Usage: llm-templates.sh [OPTIONS] <provider> <prompt>

Enhance prompts with provider-specific instructions.

OPTIONS:
    -t, --task-type TYPE    Explicitly set task type (summarization|generation|explanation|analysis|debugging|general)
    --show                  Show template for provider/task without enhancing prompt
    -h, --help              Show this help message

PROVIDERS:
    gemini      Large context specialist (concise, structured)
    codex       Code generation specialist (production-ready, best practices)
    copilot     Shell specialist (step-by-step, command-first)
    claude      Reasoning specialist (no modification needed)

TASK TYPES (auto-detected from keywords):
    summarization   summarize, summary, overview, tldr
    generation      generate, create, scaffold, crud, build
    explanation     explain, what does, how to, describe
    analysis        review, analyze, check, inspect, examine
    debugging       debug, fix, error, bug, issue, problem

EXAMPLES:
    # Auto-detect task type
    llm-templates.sh gemini "summarize this log file"

    # Explicit task type
    llm-templates.sh -t generation codex "create REST API for User"

    # Show template only
    llm-templates.sh --show gemini summarization

    # Use in scripts
    enhanced=$(llm-templates.sh gemini "analyze dependencies")

SOURCING:
    source ~/.claude/scripts/lib/llm-templates.sh
    enhanced=$(enhance_prompt gemini "" "your prompt here")
    template=$(get_template codex generation prefix)
EOF
}

# CLI interface
main() {
    local task_type=""
    local show_only=false

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--task-type)
                task_type="$2"
                shift 2
                ;;
            --show)
                show_only=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -*)
                echo "Error: Unknown option: $1" >&2
                show_usage >&2
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done

    # Validate arguments
    if [[ $# -lt 1 ]]; then
        echo "Error: Missing provider argument" >&2
        show_usage >&2
        exit 1
    fi

    local provider="$1"
    shift

    # Show template only
    if [[ "$show_only" == true ]]; then
        if [[ -z "$task_type" ]]; then
            echo "Error: --show requires -t/--task-type" >&2
            exit 1
        fi
        get_template "$provider" "$task_type" "prefix"
        local suffix=$(get_template "$provider" "$task_type" "suffix")
        if [[ -n "$suffix" ]]; then
            echo "---"
            echo "$suffix"
        fi
        exit 0
    fi

    # Need prompt for enhancement
    if [[ $# -lt 1 ]]; then
        echo "Error: Missing prompt argument" >&2
        show_usage >&2
        exit 1
    fi

    local prompt="$*"

    # Enhance and output
    enhance_prompt "$provider" "$task_type" "$prompt"
}

# Run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]]; then
    main "$@"
fi
