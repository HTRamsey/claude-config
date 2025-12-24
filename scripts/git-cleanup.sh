#!/usr/bin/env bash
# git-cleanup.sh - Git maintenance and cleanup utilities
#
# Usage:
#   git-cleanup.sh branches       List merged branches that can be deleted
#   git-cleanup.sh branches --delete  Actually delete them
#   git-cleanup.sh stale          Find stale branches (>30 days inactive)
#   git-cleanup.sh orphans        Find orphaned commits
#   git-cleanup.sh gc             Run garbage collection
#   git-cleanup.sh all            Run all cleanup operations

SCRIPT_VERSION="1.0.0"

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Protected branches (never delete)
PROTECTED="main master develop release"

show_help() {
    cat << 'EOF'
git-cleanup.sh - Git maintenance and cleanup utilities

Usage:
  git-cleanup.sh <command> [options]

Commands:
  branches          List merged branches that can be deleted
  branches --delete Actually delete merged branches
  stale             Find branches with no activity in 30+ days
  orphans           Find orphaned commits (not reachable from any branch)
  gc                Run git garbage collection
  prune             Prune remote-tracking branches
  all               Run all cleanup operations (dry-run by default)
  all --execute     Run all cleanup operations for real

Examples:
  # See what can be cleaned up
  git-cleanup.sh all

  # Delete merged branches
  git-cleanup.sh branches --delete

  # Find abandoned work
  git-cleanup.sh stale

Protected branches (never deleted): main, master, develop, release

EOF
    exit 0
}

# Check if branch is protected
is_protected() {
    local branch="$1"
    for p in $PROTECTED; do
        [[ "$branch" == "$p" ]] && return 0
    done
    return 1
}

# List merged branches
cmd_branches() {
    local delete="${1:-}"

    echo "=== Merged Branches ==="
    echo ""

    # Get current branch
    local current=$(git branch --show-current)

    # Find merged branches
    local merged=$(git branch --merged | grep -v "^\*" | grep -v -E "^\s*(main|master|develop|release)" | sed 's/^[ \t]*//')

    if [[ -z "$merged" ]]; then
        echo -e "${GREEN}No merged branches to clean up${NC}"
        return 0
    fi

    echo "Branches merged into $current:"
    echo ""

    for branch in $merged; do
        if is_protected "$branch"; then
            echo -e "  ${YELLOW}$branch${NC} (protected, skipping)"
            continue
        fi

        local last_commit=$(git log -1 --format="%cr by %an" "$branch" 2>/dev/null || echo "unknown")

        if [[ "$delete" == "--delete" ]]; then
            echo -e "  ${RED}Deleting:${NC} $branch ($last_commit)"
            git branch -d "$branch" 2>/dev/null || echo "    (failed - may need -D)"
        else
            echo -e "  ${BLUE}$branch${NC} ($last_commit)"
        fi
    done

    if [[ "$delete" != "--delete" ]]; then
        echo ""
        echo "Run 'git-cleanup.sh branches --delete' to delete these branches"
    fi
}

# Find stale branches
cmd_stale() {
    local days="${1:-30}"

    echo "=== Stale Branches (>${days} days inactive) ==="
    echo ""

    local now=$(date +%s)
    local threshold=$((now - days * 86400))
    local found=0

    for branch in $(git branch -a --format='%(refname:short)'); do
        # Skip protected
        is_protected "${branch##*/}" && continue

        local last_commit=$(git log -1 --format="%ct" "$branch" 2>/dev/null || echo "0")

        if [[ "$last_commit" -lt "$threshold" && "$last_commit" -gt 0 ]]; then
            local age=$(( (now - last_commit) / 86400 ))
            local author=$(git log -1 --format="%an" "$branch" 2>/dev/null)
            local message=$(git log -1 --format="%s" "$branch" 2>/dev/null | head -c 50)

            echo -e "${YELLOW}$branch${NC}"
            echo "  ${age} days old | $author"
            echo "  Last: $message"
            echo ""
            ((found++))
        fi
    done

    if [[ $found -eq 0 ]]; then
        echo -e "${GREEN}No stale branches found${NC}"
    else
        echo "Found $found stale branches"
    fi
}

# Find orphaned commits
cmd_orphans() {
    echo "=== Orphaned Commits ==="
    echo ""

    # Find unreachable commits
    local orphans=$(git fsck --unreachable --no-reflogs 2>/dev/null | grep "commit" | head -20)

    if [[ -z "$orphans" ]]; then
        echo -e "${GREEN}No orphaned commits found${NC}"
        return 0
    fi

    echo "Unreachable commits (not on any branch):"
    echo ""

    while read -r line; do
        local sha=$(echo "$line" | awk '{print $3}')
        local info=$(git log -1 --format="%h %s (%cr)" "$sha" 2>/dev/null || echo "$sha")
        echo "  $info"
    done <<< "$orphans"

    echo ""
    echo "These can be recovered with 'git cherry-pick <sha>'"
    echo "Or permanently removed with 'git gc --prune=now'"
}

# Garbage collection
cmd_gc() {
    echo "=== Garbage Collection ==="
    echo ""

    # Show current size
    local before=$(du -sh .git 2>/dev/null | cut -f1)
    echo "Before: .git = $before"

    # Run gc
    echo "Running git gc --aggressive..."
    git gc --aggressive --prune=now

    # Show new size
    local after=$(du -sh .git 2>/dev/null | cut -f1)
    echo "After:  .git = $after"
}

# Prune remote references
cmd_prune() {
    echo "=== Pruning Remote References ==="
    echo ""

    # Show what will be pruned
    echo "Stale remote-tracking branches:"
    git remote prune origin --dry-run 2>/dev/null | grep "pruning" || echo "  (none)"

    echo ""
    echo "Pruning..."
    git remote prune origin

    echo -e "${GREEN}Done${NC}"
}

# Run all cleanup
cmd_all() {
    local execute="${1:-}"

    echo "=== Full Git Cleanup ==="
    echo ""

    if [[ "$execute" != "--execute" ]]; then
        echo -e "${YELLOW}DRY RUN - use 'all --execute' to make changes${NC}"
        echo ""
    fi

    # Fetch latest
    echo "Fetching from remote..."
    git fetch --prune 2>/dev/null || true
    echo ""

    # Run each command
    cmd_branches
    echo ""
    cmd_stale
    echo ""
    cmd_prune
    echo ""

    if [[ "$execute" == "--execute" ]]; then
        echo "Running garbage collection..."
        cmd_gc
    else
        echo "Skipping GC in dry-run mode"
    fi

    echo ""
    echo "=== Cleanup Complete ==="
}

# Main
case "${1:-}" in
    -h|--help|"")
        show_help
        ;;
    branches)
        cmd_branches "${2:-}"
        ;;
    stale)
        cmd_stale "${2:-30}"
        ;;
    orphans)
        cmd_orphans
        ;;
    gc)
        cmd_gc
        ;;
    prune)
        cmd_prune
        ;;
    all)
        cmd_all "${2:-}"
        ;;
    *)
        echo "Unknown command: $1" >&2
        echo "Run 'git-cleanup.sh --help' for usage" >&2
        exit 1
        ;;
esac
