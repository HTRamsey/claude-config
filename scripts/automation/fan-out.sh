#!/usr/bin/env bash
set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh" 2>/dev/null || source "$HOME/.claude/scripts/lib/common.sh"

usage() {
    cat << 'EOF'
Usage: fan-out.sh <prompt> <file-pattern> [--parallel N] [--dry-run]

Fan-out processing - route to appropriate tool based on scale.

Routes:
  1-2 files    Direct Claude (inline)
  3-50 files   batch-editor agent
  51+ files    Headless fan-out (parallel Claude processes)

Options:
  --parallel N  Number of parallel processes (default: 4)
  --dry-run     Preview without executing
  -h, --help    Show this help

Examples:
  fan-out.sh "Migrate to new API" "src/**/*.ts"
  fan-out.sh "Add error handling" "*.py" --parallel 4
  find . -name "*.js" | fan-out.sh "Convert to TypeScript" -
EOF
    exit 0
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

PROMPT="$1"
PATTERN="$2"
PARALLEL=4
DRY_RUN=false

# Parse flags
shift 2 || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --parallel) PARALLEL="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -) PATTERN="-"; shift ;;
        *) shift ;;
    esac
done

if [[ -z "$PROMPT" ]]; then
    echo "Usage: fan-out.sh <prompt> <file-pattern> [--parallel N] [--dry-run]"
    echo ""
    echo "Examples:"
    echo "  fan-out.sh 'Migrate to new API' 'src/**/*.ts'"
    echo "  fan-out.sh 'Add error handling' '*.py' --parallel 4"
    echo "  find . -name '*.js' | fan-out.sh 'Convert to TypeScript' -"
    exit 1
fi

# Collect files
FILES=()
if [[ "$PATTERN" == "-" ]]; then
    while IFS= read -r line; do
        [[ -n "$line" && -f "$line" ]] && FILES+=("$line")
    done
else
    # Try fd first (faster), then find, then glob
    if command -v fd &>/dev/null; then
        while IFS= read -r file; do
            [[ -n "$file" && -f "$file" ]] && FILES+=("$file")
        done < <(fd --type f "$PATTERN" 2>/dev/null)
    fi

    # If fd didn't find anything, try find with -print0
    if [[ ${#FILES[@]} -eq 0 ]]; then
        while IFS= read -r -d '' file; do
            FILES+=("$file")
        done < <(find . -path "./.git" -prune -o -type f -name "$PATTERN" -print0 2>/dev/null)
    fi

    # If find didn't work, try glob
    if [[ ${#FILES[@]} -eq 0 ]]; then
        shopt -s globstar nullglob 2>/dev/null || true
        for f in $PATTERN; do
            [[ -f "$f" ]] && FILES+=("$f")
        done
    fi
fi

COUNT=${#FILES[@]}

if [[ $COUNT -eq 0 ]]; then
    echo "No files found matching pattern: $PATTERN"
    exit 1
fi

echo "=== Fan-Out Processing ==="
echo "Prompt: $PROMPT"
echo "Files: $COUNT"
echo ""

# Route based on count
if [[ $COUNT -le 2 ]]; then
    echo "Route: Direct (inline, $COUNT files)"
    echo ""
    if $DRY_RUN; then
        echo "[DRY RUN] Would process inline:"
        printf '%s\n' "${FILES[@]}"
    else
        # Single Claude call with all files
        claude -p "$PROMPT

Files to process:
$(printf '%s\n' "${FILES[@]}")"
    fi

elif [[ $COUNT -le 50 ]]; then
    echo "Route: batch-editor agent ($COUNT files)"
    echo ""
    if $DRY_RUN; then
        echo "[DRY RUN] Would use batch-editor for:"
        printf '%s\n' "${FILES[@]}"
    else
        # Use batch-editor agent
        claude -p "Use the batch-editor agent to: $PROMPT

Target files:
$(printf '%s\n' "${FILES[@]}")"
    fi

else
    echo "Route: Headless fan-out ($COUNT files, $PARALLEL parallel)"
    echo ""

    # Create task list
    TASK_FILE=$(mktemp)
    printf '%s\n' "${FILES[@]}" > "$TASK_FILE"

    if $DRY_RUN; then
        echo "[DRY RUN] Would spawn $PARALLEL parallel processes for:"
        head -10 "$TASK_FILE"
        [[ $COUNT -gt 10 ]] && echo "... and $((COUNT - 10)) more"
        rm "$TASK_FILE"
        exit 0
    fi

    echo "Processing in batches of $PARALLEL..."
    echo ""

    # Process in parallel batches
    COMPLETED=0
    FAILED=0

    process_file() {
        local file="$1"
        local result
        if result=$(claude -p "$PROMPT

File: $file" --max-turns 10 2>&1); then
            echo "✓ $file"
            return 0
        else
            echo "✗ $file: $result" >&2
            return 1
        fi
    }

    export -f process_file
    export PROMPT

    # Use xargs for parallel execution (PROMPT already exported above)
    if command -v parallel &>/dev/null; then
        parallel -j "$PARALLEL" --bar bash -c 'claude -p "$PROMPT

File: $1" --max-turns 10' _ {} :::: "$TASK_FILE"
    else
        # Fallback: xargs (use environment variable for prompt to avoid injection)
        export PROMPT
        xargs -P "$PARALLEL" -I {} bash -c '
            if claude -p "$PROMPT

File: $1" --max-turns 10 >/dev/null 2>&1; then
                echo "✓ $1"
            else
                echo "✗ $1" >&2
            fi
        ' _ {} < "$TASK_FILE"
    fi

    rm "$TASK_FILE"
    echo ""
    echo "Fan-out complete."
fi
