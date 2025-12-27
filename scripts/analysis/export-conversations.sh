#!/usr/bin/env bash
set -euo pipefail
# export-conversations.sh - Export Claude conversations to readable markdown
#
# Usage:
#   export-conversations.sh                    # Export last 7 days
#   export-conversations.sh --days 30          # Export last 30 days
#   export-conversations.sh --session <id>     # Export specific session
#   export-conversations.sh --list             # List available sessions

PROJECTS_DIR="$HOME/.claude/projects"
OUTPUT_DIR="$HOME/.claude/data/exports"
DAYS=7

usage() {
    sed -n '3,8p' "$0" | sed 's/^# //'
    exit 0
}

SESSION_ID=""
LIST_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --days|-d) DAYS="$2"; shift 2 ;;
        --session|-s) SESSION_ID="$2"; shift 2 ;;
        --output|-o) OUTPUT_DIR="$2"; shift 2 ;;
        --list|-l) LIST_ONLY=true; shift ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

mkdir -p "$OUTPUT_DIR"

# Find session files (exclude agent transcripts)
if [[ -n "$SESSION_ID" ]]; then
    mapfile -t FILES < <(find "$PROJECTS_DIR" -name "*${SESSION_ID}*.jsonl" 2>/dev/null)
else
    mapfile -t FILES < <(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -"$DAYS" 2>/dev/null | grep -v "/agent-" || true)
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "No conversations found"
    exit 0
fi

# List mode
if [[ "$LIST_ONLY" == "true" ]]; then
    echo "Sessions from last $DAYS days (${#FILES[@]} found):"
    echo ""
    for file in "${FILES[@]}"; do
        [[ -z "$file" ]] && continue
        session=$(basename "$file" .jsonl)
        date=$(stat -c %y "$file" | cut -d' ' -f1)
        # Get summary from file if exists, otherwise first user message
        summary=$(jq -r 'select(.type=="summary") | .summary' "$file" 2>/dev/null | head -1)
        if [[ -z "$summary" ]]; then
            summary=$(jq -r 'select(.type=="user") | .message.content | if type=="string" then .[0:50] else "" end' "$file" 2>/dev/null | head -1)
        fi
        [[ -z "$summary" ]] && summary="(no title)"
        printf "%s  %-8s  %.55s\n" "$date" "${session:0:8}" "$summary"
    done | sort -r | head -30
    exit 0
fi

# Export conversations
count=0
for file in "${FILES[@]}"; do
    [[ -z "$file" ]] && continue

    session=$(basename "$file" .jsonl)
    project=$(basename "$(dirname "$file")")
    date=$(stat -c %y "$file" | cut -d' ' -f1)

    # Skip agent transcripts
    [[ "$session" == agent-* ]] && continue

    output_file="$OUTPUT_DIR/${date}_${session:0:8}.md"

    {
        echo "# Conversation: ${session:0:8}"
        echo ""
        echo "**Date:** $date"
        echo "**Project:** ${project//-/\/}"
        echo "**Session:** $session"
        echo ""

        # Get summary if available
        summary=$(jq -r 'select(.type=="summary") | .summary' "$file" 2>/dev/null | head -1)
        if [[ -n "$summary" ]]; then
            echo "**Summary:** $summary"
            echo ""
        fi

        echo "---"
        echo ""

        # Extract messages (simplified, focused on readability)
        jq -r '
            select(.type == "user" or .type == "assistant") |
            if .type == "user" then
                "## Human\n\n" + (
                    if (.message.content | type) == "string" then
                        .message.content
                    elif (.message.content | type) == "array" then
                        ([.message.content[] | select(.type == "text") | .text] | join("\n"))
                    else
                        "(complex)"
                    end
                ) + "\n"
            else
                "## Assistant\n\n" + (
                    if (.message.content | type) == "array" then
                        ([.message.content[] |
                            if .type == "text" then .text
                            elif .type == "tool_use" then "[Tool: " + .name + "]"
                            else ""
                            end
                        ] | map(select(. != "")) | join("\n\n"))
                    elif (.message.content | type) == "string" then
                        .message.content
                    else
                        "(complex)"
                    end
                ) + "\n"
            end
        ' "$file" 2>/dev/null || echo "(parse error)"

    } > "$output_file"

    count=$((count + 1))
    echo "Exported: $output_file"
done

echo ""
echo "Exported $count conversations to $OUTPUT_DIR"
