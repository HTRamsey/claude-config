#!/usr/bin/env bash
# project-stats.sh - Quick project statistics using tokei
# Usage: project-stats.sh [path] [options]
#
# Features:
# - Auto-excludes common noise directories
# - Compact output mode
# - Filter by language
# - JSON output for processing

set -euo pipefail

path="${1:-.}"
option="${2:-}"
filter="${3:-}"

# Find tokei
TOKEI=""
if command -v tokei &>/dev/null; then
    TOKEI="tokei"
elif [[ -x "$HOME/.cargo/bin/tokei" ]]; then
    TOKEI="$HOME/.cargo/bin/tokei"
fi

if [[ -z "$TOKEI" ]]; then
    echo "Error: tokei not found. Install with: cargo install tokei"
    exit 1
fi

show_help() {
    cat << 'EOF'
Usage: project-stats.sh [path] [options] [language-filter]

Options:
  (none)      Full stats with standard excludes
  compact     One-line-per-language format
  json        JSON output for processing
  summary     Just totals
  languages   List detected languages

Examples:
  project-stats.sh                    # Current directory
  project-stats.sh ./src              # Specific path
  project-stats.sh . compact          # Compact output
  project-stats.sh . summary          # Just totals
  project-stats.sh ./src json Python  # JSON, Python only

EOF
    exit 0
}

[[ "$path" == "-h" || "$path" == "--help" ]] && show_help

# Standard excludes for cleaner output
excludes=(
    "node_modules"
    ".git"
    "vendor"
    "dist"
    "build"
    "target"
    "__pycache__"
    ".venv"
    "venv"
    "coverage"
    ".next"
    ".cache"
)

# Build exclude args
exclude_args=""
for ex in "${excludes[@]}"; do
    exclude_args="$exclude_args --exclude $ex"
done

case "$option" in
    compact)
        # Compact one-line-per-language
        $TOKEI $exclude_args "$path" --compact 2>/dev/null
        ;;
    json)
        # JSON output, optionally filtered
        if [[ -n "$filter" ]]; then
            $TOKEI $exclude_args "$path" -o json 2>/dev/null | jq ".\"$filter\" // empty"
        else
            $TOKEI $exclude_args "$path" -o json 2>/dev/null | jq -c 'to_entries | map({language: .key, files: .value.reports // .value | length, code: .value.code // 0}) | sort_by(-.code)'
        fi
        ;;
    summary)
        # Just the totals
        output=$($TOKEI $exclude_args "$path" 2>/dev/null)
        echo "$output" | tail -4
        ;;
    languages)
        # List languages found
        $TOKEI $exclude_args "$path" -o json 2>/dev/null | jq -r 'keys[]' | sort
        ;;
    *)
        # Default: full output
        $TOKEI $exclude_args "$path" 2>/dev/null
        ;;
esac
