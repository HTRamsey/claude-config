#!/usr/bin/env bash
# session-picker.sh - Browse, search, and resume Claude sessions
#
# Usage:
#   session-picker.sh list [n]        List recent sessions (default: 10)
#   session-picker.sh search <term>   Search sessions by content
#   session-picker.sh info <id>       Show session details
#   session-picker.sh resume <n|id>   Resume session by number or ID
#   session-picker.sh clean [days]    Remove old sessions (default: 30 days)
#
# Sessions are stored in ~/.claude/projects/

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

PROJECTS_DIR="$HOME/.claude/projects"
HISTORY_FILE="$HOME/.claude/data/session-history.json"

show_help() {
    cat << 'EOF'
session-picker.sh - Browse, search, and resume Claude sessions

Usage:
  session-picker.sh <command> [args]

Commands:
  list [n]         List n most recent sessions (default: 10)
  search <term>    Search session content for term
  info <id>        Show session details and first message
  resume <n|id>    Resume by list number or session ID
  projects         List all project directories
  clean [days]     Remove sessions older than n days (default: 30)

Examples:
  session-picker.sh list              # Show 10 recent sessions
  session-picker.sh list 20           # Show 20 recent sessions
  session-picker.sh search "auth"     # Find sessions mentioning auth
  session-picker.sh info 3            # Info on session #3 from list
  session-picker.sh resume 1          # Resume most recent session
  session-picker.sh resume abc123     # Resume by session ID

EOF
    exit 0
}

# Get session files sorted by modification time (newest first)
get_sessions() {
    local limit="${1:-10}"
    find "$PROJECTS_DIR" -name "*.jsonl" -type f -size +0 2>/dev/null | \
        xargs -r ls -t 2>/dev/null | \
        head -"$limit"
}

# Extract first user message from session
get_first_message() {
    local file="$1"
    # Find first user message and extract content
    local msg=$(grep -m1 '"role":"user"' "$file" 2>/dev/null | \
        sed 's/.*"content":\s*"//' | \
        sed 's/".*//' | \
        head -c 80 | tr '\n' ' ' | tr -d '\\')
    # Fallback: try jq if sed didn't work
    if [[ -z "$msg" || "$msg" == *"{"* ]]; then
        msg=$(grep -m1 '"role":"user"' "$file" 2>/dev/null | \
            jq -r 'if .content then (if type == "array" then .[0].text else .content end) else .message end' 2>/dev/null | \
            head -c 80 | tr '\n' ' ')
    fi
    echo "${msg:-<empty>}"
}

# Get session ID from file path
get_session_id() {
    basename "$1" .jsonl
}

# Get project from file path
get_project() {
    local dir=$(dirname "$1")
    basename "$dir" | sed 's/-home-jonglaser-/~/g; s/--/\//g; s/-/\//g'
}

# Format file size
format_size() {
    local size="$1"
    if [[ $size -gt 1048576 ]]; then
        echo "$((size / 1048576))MB"
    elif [[ $size -gt 1024 ]]; then
        echo "$((size / 1024))KB"
    else
        echo "${size}B"
    fi
}

# List recent sessions
cmd_list() {
    local limit="${1:-10}"
    echo "=== Recent Sessions (last $limit) ==="
    echo ""
    printf "%-3s %-20s %-8s %-12s %s\n" "#" "Modified" "Size" "Project" "First Message"
    printf "%s\n" "$(printf '%.0s-' {1..80})"

    local n=1
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue

        local id=$(get_session_id "$file")
        local project=$(get_project "$file")
        local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
        local mtime=$(stat -c%y "$file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || date -r "$file" "+%Y-%m-%d %H:%M" 2>/dev/null)
        local msg=$(get_first_message "$file")

        # Truncate for display
        project="${project:0:12}"
        msg="${msg:0:35}"

        printf "%-3s %-20s %-8s %-12s %s\n" "$n" "$mtime" "$(format_size $size)" "$project" "$msg"
        ((n++))
    done < <(get_sessions "$limit")

    echo ""
    echo "Use 'session-picker.sh resume <n>' to resume a session"
}

# Search sessions
cmd_search() {
    local term="$1"
    if [[ -z "$term" ]]; then
        echo "Usage: session-picker.sh search <term>"
        exit 1
    fi

    echo "=== Sessions matching '$term' ==="
    echo ""

    local found=0
    while IFS= read -r file; do
        if grep -q "$term" "$file" 2>/dev/null; then
            local id=$(get_session_id "$file")
            local project=$(get_project "$file")
            local mtime=$(stat -c%y "$file" 2>/dev/null | cut -d' ' -f1 || date -r "$file" "+%Y-%m-%d" 2>/dev/null)

            echo "[$mtime] $project"
            echo "  ID: $id"
            echo "  Match: $(grep -m1 "$term" "$file" 2>/dev/null | jq -r '.message // .content // .' 2>/dev/null | head -c 100 | tr '\n' ' ')"
            echo ""
            ((found++))
        fi
    done < <(get_sessions 100)

    if [[ $found -eq 0 ]]; then
        echo "No sessions found matching '$term'"
    else
        echo "Found $found session(s)"
    fi
}

# Show session info
cmd_info() {
    local target="$1"
    if [[ -z "$target" ]]; then
        echo "Usage: session-picker.sh info <n|id>"
        exit 1
    fi

    local file=""

    # If numeric, get from list
    if [[ "$target" =~ ^[0-9]+$ ]]; then
        file=$(get_sessions 100 | sed -n "${target}p")
    else
        # Search by ID
        file=$(find "$PROJECTS_DIR" -name "${target}*.jsonl" -type f 2>/dev/null | head -1)
    fi

    if [[ -z "$file" || ! -f "$file" ]]; then
        echo "Session not found: $target"
        exit 1
    fi

    local id=$(get_session_id "$file")
    local project=$(get_project "$file")
    local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
    local mtime=$(stat -c%y "$file" 2>/dev/null || date -r "$file" 2>/dev/null)
    local lines=$(wc -l < "$file")

    echo "=== Session Info ==="
    echo ""
    echo "ID:       $id"
    echo "Project:  $project"
    echo "File:     $file"
    echo "Size:     $(format_size $size)"
    echo "Modified: $mtime"
    echo "Messages: ~$lines"
    echo ""
    echo "=== First User Message ==="
    grep -m1 '"role":"user"' "$file" 2>/dev/null | jq -r '.message // .content // ""' 2>/dev/null | head -20 || echo "(empty)"
    echo ""
    echo "Resume with: claude --resume $id"
}

# Resume session
cmd_resume() {
    local target="$1"
    if [[ -z "$target" ]]; then
        echo "Usage: session-picker.sh resume <n|id>"
        exit 1
    fi

    local session_id=""

    # If numeric, get from list
    if [[ "$target" =~ ^[0-9]+$ ]]; then
        local file=$(get_sessions 100 | sed -n "${target}p")
        if [[ -n "$file" ]]; then
            session_id=$(get_session_id "$file")
        fi
    else
        session_id="$target"
    fi

    if [[ -z "$session_id" ]]; then
        echo "Session not found: $target"
        exit 1
    fi

    echo "Resuming session: $session_id"
    echo "Running: claude --resume $session_id"
    echo ""

    exec claude --resume "$session_id"
}

# List project directories
cmd_projects() {
    echo "=== Project Directories ==="
    echo ""

    for dir in "$PROJECTS_DIR"/*/; do
        [[ ! -d "$dir" ]] && continue
        local name=$(basename "$dir")
        local count=$(find "$dir" -name "*.jsonl" -type f 2>/dev/null | wc -l)
        local decoded=$(echo "$name" | sed 's/-home-jonglaser-/~/g; s/--/\//g; s/-/\//g')
        printf "%-40s %3d sessions\n" "$decoded" "$count"
    done
}

# Clean old sessions
cmd_clean() {
    local days="${1:-30}"
    echo "=== Cleaning sessions older than $days days ==="
    echo ""

    local count=0
    local total_size=0

    while IFS= read -r file; do
        local size=$(stat -c%s "$file" 2>/dev/null || echo "0")
        echo "Would remove: $file ($(format_size $size))"
        ((count++))
        ((total_size += size))
    done < <(find "$PROJECTS_DIR" -name "*.jsonl" -type f -mtime +"$days" 2>/dev/null)

    if [[ $count -eq 0 ]]; then
        echo "No sessions older than $days days"
    else
        echo ""
        echo "Found $count sessions ($(format_size $total_size) total)"
        echo ""
        read -p "Delete these sessions? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            find "$PROJECTS_DIR" -name "*.jsonl" -type f -mtime +"$days" -delete 2>/dev/null
            echo "Deleted $count sessions"
        else
            echo "Cancelled"
        fi
    fi
}

# Main
case "${1:-}" in
    -h|--help|"") show_help ;;
    list) shift; cmd_list "$@" ;;
    search) shift; cmd_search "$@" ;;
    info) shift; cmd_info "$@" ;;
    resume) shift; cmd_resume "$@" ;;
    projects) cmd_projects ;;
    clean) shift; cmd_clean "$@" ;;
    *)
        echo "Unknown command: $1"
        echo "Try: session-picker.sh --help"
        exit 1
        ;;
esac
