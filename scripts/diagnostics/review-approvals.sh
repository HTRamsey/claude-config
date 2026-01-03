#!/usr/bin/env bash
#
# Review manual approvals logged by approval_tracker.py
#
# Usage:
#   review-approvals.sh           # Show summary
#   review-approvals.sh -d 7      # Last 7 days only
#   review-approvals.sh -v        # Verbose (show all entries)
#   review-approvals.sh -s        # Suggest settings.json additions
#   review-approvals.sh -c        # Clean up log (archive old entries)
#
set -euo pipefail

APPROVALS_FILE="$HOME/.claude/data/manual-approvals.jsonl"
THRESHOLD=3  # Minimum count to suggest for auto-approve

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Review manual approvals logged by approval_tracker.py.
Helps identify patterns that could be added to settings.json allowlist.

Options:
  -d DAYS     Only show last N days (default: all)
  -v          Verbose - show all entries
  -s          Suggest settings.json additions
  -t N        Set suggestion threshold (default: 3)
  -c          Clean - archive entries older than 30 days
  -h          Show this help

Examples:
  $(basename "$0")              # Summary of all approvals
  $(basename "$0") -d 7         # Last 7 days
  $(basename "$0") -s           # Suggest additions to settings.json
  $(basename "$0") -s -t 5      # Suggest with threshold of 5
EOF
}

# Parse arguments
DAYS=""
VERBOSE=false
SUGGEST=false
CLEAN=false

while getopts "d:vst:ch" opt; do
    case $opt in
        d) DAYS="$OPTARG" ;;
        v) VERBOSE=true ;;
        s) SUGGEST=true ;;
        t) THRESHOLD="$OPTARG" ;;
        c) CLEAN=true ;;
        h) usage; exit 0 ;;
        *) usage; exit 1 ;;
    esac
done

# Check if file exists
if [[ ! -f "$APPROVALS_FILE" ]]; then
    echo "No manual approvals logged yet."
    echo "File: $APPROVALS_FILE"
    exit 0
fi

# Clean old entries
if $CLEAN; then
    CUTOFF=$(date -d "30 days ago" +%Y-%m-%dT00:00:00 2>/dev/null || date -v-30d +%Y-%m-%dT00:00:00)
    ARCHIVE_FILE="$HOME/.claude/data/manual-approvals-archive.jsonl"

    # Move old entries to archive
    while IFS= read -r line; do
        ts=$(echo "$line" | jq -r '.timestamp // empty')
        if [[ -n "$ts" && "$ts" < "$CUTOFF" ]]; then
            echo "$line" >> "$ARCHIVE_FILE"
        fi
    done < "$APPROVALS_FILE"

    # Keep only recent entries
    jq -c "select(.timestamp >= \"$CUTOFF\")" "$APPROVALS_FILE" > "${APPROVALS_FILE}.tmp" 2>/dev/null || true
    mv "${APPROVALS_FILE}.tmp" "$APPROVALS_FILE"

    echo "Archived entries older than 30 days to: $ARCHIVE_FILE"
    exit 0
fi

# Filter by date if specified
if [[ -n "$DAYS" ]]; then
    CUTOFF=$(date -d "$DAYS days ago" +%Y-%m-%dT00:00:00 2>/dev/null || date -v-${DAYS}d +%Y-%m-%dT00:00:00)
    DATA=$(jq -c "select(.timestamp >= \"$CUTOFF\")" "$APPROVALS_FILE" 2>/dev/null || cat "$APPROVALS_FILE")
else
    DATA=$(cat "$APPROVALS_FILE")
fi

TOTAL=$(echo "$DATA" | wc -l | tr -d ' ')
echo "=== Manual Approval Summary ==="
echo "Total approvals: $TOTAL"
echo

# Show verbose listing
if $VERBOSE; then
    echo "=== All Entries ==="
    echo "$DATA" | jq -r '[.timestamp[0:19], .tool, .key] | @tsv' | column -t -s $'\t'
    echo
fi

# Group by tool
echo "=== By Tool ==="
echo "$DATA" | jq -r '.tool' | sort | uniq -c | sort -rn
echo

# Top Bash commands (by prefix)
echo "=== Top Bash Command Prefixes ==="
echo "$DATA" | jq -r 'select(.tool == "Bash") | .key' | \
    sed 's/ .*//' | sort | uniq -c | sort -rn | head -20
echo

# Top file paths (by directory)
echo "=== Top File Directories ==="
echo "$DATA" | jq -r 'select(.tool != "Bash") | .key' | \
    xargs -I{} dirname {} 2>/dev/null | sort | uniq -c | sort -rn | head -20
echo

# Suggestions for settings.json
if $SUGGEST; then
    echo "=== Suggested Additions to settings.json ==="
    echo "(Patterns with $THRESHOLD+ occurrences)"
    echo

    echo "# Bash commands to consider:"
    echo "$DATA" | jq -r 'select(.tool == "Bash") | .key' | \
        sed 's/ .*//' | sort | uniq -c | sort -rn | \
        awk -v t="$THRESHOLD" '$1 >= t {printf "\"Bash(%s:*)\",  # %d occurrences\n", $2, $1}'
    echo

    echo "# File patterns to review:"
    echo "$DATA" | jq -r 'select(.tool != "Bash") | "\(.tool):\(.key)"' | \
        sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | \
        awk -v t="$THRESHOLD" '$1 >= t {print "  " $0}'
    echo

    echo "Add suggested Bash patterns to ~/.claude/settings.json under:"
    echo "  permissions.allow"
    echo
    echo "For file patterns, consider adding to ~/.claude/hooks/config.py under:"
    echo "  SmartPermissions.WRITE_PATTERNS or SmartPermissions.READ_PATTERNS"
fi
