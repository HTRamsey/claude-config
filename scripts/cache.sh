#!/usr/bin/env bash
# cache.sh - Transparent caching for expensive operations
#
# Usage:
#   cache.sh <ttl_seconds> <key> <command...>
#   cache.sh 3600 "project-deps" npm list --depth=0
#   cache.sh 300 "git-status-$(pwd)" git status --porcelain
#
# Options:
#   cache.sh --clear <key>     Clear specific cache entry
#   cache.sh --clear-all       Clear all cached entries
#   cache.sh --list            List all cached entries
#   cache.sh --get <key>       Get cached value without running command
#
SCRIPT_VERSION="1.0.0"
#
# Features:
#   - File-based caching with TTL
#   - Automatic key hashing for safe filenames
#   - Cache stats tracking
#   - Fallback to command on cache miss

set -euo pipefail

CACHE_DIR="${CLAUDE_CACHE_DIR:-${TMPDIR:-/tmp}/claude-cache-$(id -u)}"
STATS_FILE="$CACHE_DIR/.stats"

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"

# Hash key to safe filename
hash_key() {
    echo "$1" | md5sum | cut -d' ' -f1
}

# Get cache file path
cache_file() {
    echo "$CACHE_DIR/$(hash_key "$1")"
}

# Get file mtime portably (Linux and macOS)
get_mtime() {
    local file="$1"
    stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null || echo 0
}

# Check if cache is valid (exists and not expired)
cache_valid() {
    local file="$1"
    local ttl="$2"

    [[ ! -f "$file" ]] && return 1

    local now=$(date +%s)
    local mtime=$(get_mtime "$file")
    local age=$((now - mtime))

    [[ $age -lt $ttl ]]
}

# Update stats
update_stats() {
    local type="$1"
    local key="$2"

    local hits=0 misses=0
    if [[ -f "$STATS_FILE" ]]; then
        hits=$(grep -c "^hit:" "$STATS_FILE" 2>/dev/null || echo 0)
        misses=$(grep -c "^miss:" "$STATS_FILE" 2>/dev/null || echo 0)
    fi

    echo "${type}:${key}:$(date +%s)" >> "$STATS_FILE"

    # Trim stats file if too large
    if [[ $(wc -l < "$STATS_FILE") -gt 1000 ]]; then
        tail -500 "$STATS_FILE" > "$STATS_FILE.tmp"
        mv "$STATS_FILE.tmp" "$STATS_FILE"
    fi
}

# Show usage
show_help() {
    cat << 'EOF'
cache.sh - Transparent caching for expensive operations

Usage:
  cache.sh <ttl_seconds> <key> <command...>

Options:
  --clear <key>    Clear specific cache entry
  --clear-all      Clear all cached entries
  --list           List all cached entries with age
  --stats          Show cache hit/miss statistics
  --get <key>      Get cached value without running command

Examples:
  # Cache npm list for 1 hour
  cache.sh 3600 "npm-deps" npm list --depth=0

  # Cache git status for 5 minutes (include pwd in key for uniqueness)
  cache.sh 300 "git-status-$(pwd | md5sum | cut -c1-8)" git status

  # Cache project file list for 10 minutes
  cache.sh 600 "project-files" find . -name "*.py" -type f

  # Clear a specific cache entry
  cache.sh --clear "npm-deps"

  # See what's cached
  cache.sh --list

TTL Guidelines:
  60     - 1 minute (rapidly changing)
  300    - 5 minutes (git status, file lists)
  3600   - 1 hour (dependencies, project structure)
  86400  - 1 day (rarely changing)

EOF
    exit 0
}

# Handle options
case "${1:-}" in
    -h|--help)
        show_help
        ;;
    --clear)
        key="${2:?Missing key}"
        file=$(cache_file "$key")
        if [[ -f "$file" ]]; then
            rm -f "$file"
            echo "Cleared cache for: $key"
        else
            echo "No cache entry for: $key"
        fi
        exit 0
        ;;
    --clear-all)
        # Safety check: ensure CACHE_DIR is set, non-empty, and not a system path
        if [[ -z "${CACHE_DIR:-}" || "$CACHE_DIR" == "/" || "$CACHE_DIR" == "/tmp" ]]; then
            echo "Error: Invalid cache directory: $CACHE_DIR" >&2
            exit 1
        fi
        if [[ -d "$CACHE_DIR" ]]; then
            # Use find for safer deletion than rm -rf with glob
            find "$CACHE_DIR" -mindepth 1 -delete 2>/dev/null || rm -rf "${CACHE_DIR:?}"/*
            echo "Cleared all cache entries"
        else
            echo "Cache directory does not exist"
        fi
        exit 0
        ;;
    --list)
        echo "=== Cached Entries ==="
        for f in "$CACHE_DIR"/*; do
            [[ -f "$f" ]] || continue
            [[ "$(basename "$f")" == ".stats" ]] && continue
            age=$(( $(date +%s) - $(get_mtime "$f") ))
            size=$(wc -c < "$f")
            echo "  $(basename "$f"): ${age}s old, ${size} bytes"
        done | head -20
        echo ""
        echo "Cache dir: $CACHE_DIR"
        exit 0
        ;;
    --stats)
        if [[ -f "$STATS_FILE" ]]; then
            hits=$(grep -c "^hit:" "$STATS_FILE" 2>/dev/null || echo 0)
            misses=$(grep -c "^miss:" "$STATS_FILE" 2>/dev/null || echo 0)
            total=$((hits + misses))
            if [[ $total -gt 0 ]]; then
                rate=$((hits * 100 / total))
                echo "Cache Statistics:"
                echo "  Hits: $hits"
                echo "  Misses: $misses"
                echo "  Hit rate: ${rate}%"
            else
                echo "No cache statistics yet"
            fi
        else
            echo "No cache statistics yet"
        fi
        exit 0
        ;;
    --get)
        key="${2:?Missing key}"
        file=$(cache_file "$key")
        if [[ -f "$file" ]]; then
            cat "$file"
        else
            echo "No cache entry for: $key" >&2
            exit 1
        fi
        exit 0
        ;;
esac

# Main caching logic
ttl="${1:?Missing TTL (seconds)}"
key="${2:?Missing cache key}"
shift 2

if [[ $# -eq 0 ]]; then
    echo "Error: No command specified" >&2
    exit 1
fi

file=$(cache_file "$key")

# Check cache
if cache_valid "$file" "$ttl"; then
    update_stats "hit" "$key"
    cat "$file"
else
    update_stats "miss" "$key"
    # Run command and cache output
    output=$("$@" 2>&1) || {
        # Don't cache errors
        echo "$output"
        exit 1
    }
    echo "$output" > "$file"
    echo "$output"
fi
