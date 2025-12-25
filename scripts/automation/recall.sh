#!/usr/bin/env bash
# recall.sh - Search past Claude Code sessions
# Usage: recall.sh <search_term> [--project <path>] [--last <n>] [--context <lines>]

set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh" 2>/dev/null || source "$HOME/.claude/scripts/lib/common.sh"

SEARCH_TERM=""
PROJECT_FILTER=""
LAST_N=10
CONTEXT_LINES=2

while [[ $# -gt 0 ]]; do
    case $1 in
        --project|-p)
            PROJECT_FILTER="$2"
            shift 2
            ;;
        --last|-l)
            LAST_N="$2"
            shift 2
            ;;
        --context|-C)
            CONTEXT_LINES="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: recall.sh <search_term> [options]"
            echo ""
            echo "Search past Claude Code sessions for context."
            echo ""
            echo "Options:"
            echo "  --project, -p <path>  Filter to specific project path"
            echo "  --last, -l <n>        Search last N sessions (default: 10)"
            echo "  --context, -C <n>     Show N lines of context (default: 2)"
            echo ""
            echo "Examples:"
            echo "  recall.sh 'authentication'           # Search all sessions"
            echo "  recall.sh 'api design' --last 5      # Last 5 sessions only"
            echo "  recall.sh 'error' -p ~/.claude       # Specific project"
            exit 0
            ;;
        *)
            SEARCH_TERM="$1"
            shift
            ;;
    esac
done

if [[ -z "$SEARCH_TERM" ]]; then
    echo "Error: Search term required"
    echo "Usage: recall.sh <search_term> [--project <path>] [--last <n>]"
    exit 1
fi

PROJECTS_DIR="$HOME/.claude/projects"

if [[ ! -d "$PROJECTS_DIR" ]]; then
    echo "No session history found."
    exit 0
fi

# Find session files
# Portable find with mtime sorting (works on Linux and macOS)
find_sorted_by_mtime() {
    local dir="$1"
    local limit="$2"
    # Try GNU find -printf first, fall back to stat-based sorting
    if find "$dir" -name "*.jsonl" -type f -printf '%T@ %p\n' 2>/dev/null | head -1 | grep -q .; then
        find "$dir" -name "*.jsonl" -type f -printf '%T@ %p\n' | sort -rn | head -n "$limit" | cut -d' ' -f2-
    else
        # macOS/BSD fallback using stat
        find "$dir" -name "*.jsonl" -type f -exec stat -f '%m %N' {} \; 2>/dev/null | sort -rn | head -n "$limit" | cut -d' ' -f2-
    fi
}

find_sessions() {
    local sessions=()

    if [[ -n "$PROJECT_FILTER" ]]; then
        # Convert path to Claude's encoding format
        local encoded_path
        encoded_path=$(echo "$PROJECT_FILTER" | sed 's|/|-|g' | sed 's|^-||')
        local project_dir="$PROJECTS_DIR/-$encoded_path"

        if [[ -d "$project_dir" ]]; then
            while IFS= read -r f; do
                [[ -n "$f" ]] && sessions+=("$f")
            done < <(find_sorted_by_mtime "$project_dir" "$LAST_N")
        fi
    else
        while IFS= read -r f; do
            [[ -n "$f" ]] && sessions+=("$f")
        done < <(find_sorted_by_mtime "$PROJECTS_DIR" "$LAST_N")
    fi

    printf '%s\n' "${sessions[@]}"
}

# Search and display results
search_sessions() {
    local found=0

    while IFS= read -r session_file; do
        [[ -z "$session_file" ]] && continue

        # Extract project path from directory name
        local project_dir
        project_dir=$(dirname "$session_file")
        local project_name
        project_name=$(basename "$project_dir" | sed 's|^-||' | sed 's|-|/|g')

        # Search for term in session (case-insensitive)
        local matches
        matches=$(grep -i -n "$SEARCH_TERM" "$session_file" 2>/dev/null | head -5) || true

        if [[ -n "$matches" ]]; then
            found=$((found + 1))
            local session_id
            session_id=$(basename "$session_file" .jsonl)
            local session_date
            session_date=$(stat -c %y "$session_file" 2>/dev/null | cut -d' ' -f1 || \
                          stat -f '%Sm' -t '%Y-%m-%d' "$session_file" 2>/dev/null)

            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "📁 Project: /$project_name"
            echo "📅 Date: $session_date"
            echo "🔑 Session: ${session_id:0:8}..."
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            # Show context around matches
            echo "$matches" | while IFS= read -r match; do
                local line_num
                line_num=$(echo "$match" | cut -d: -f1)

                # Extract and pretty-print the JSON content
                local content
                content=$(sed -n "${line_num}p" "$session_file" 2>/dev/null)

                # Try to extract human-readable content using jq (portable, no grep -P)
                local text
                text=$(echo "$content" | jq -r '.content // .text // empty' 2>/dev/null | head -1)
                # Fallback to raw match if jq fails
                [[ -z "$text" ]] && text=$(echo "$match" | cut -d: -f2- | head -c 200)

                if [[ -n "$text" ]]; then
                    # Highlight search term
                    echo "  → $(echo "$text" | head -c 300 | grep -i --color=always "$SEARCH_TERM" 2>/dev/null || echo "$text" | head -c 300)"
                fi
            done
        fi
    done < <(find_sessions)

    if [[ $found -eq 0 ]]; then
        echo "No matches found for '$SEARCH_TERM'"
    else
        echo ""
        echo "Found matches in $found session(s)"
    fi
}

search_sessions
