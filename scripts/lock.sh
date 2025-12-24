#!/usr/bin/env bash
# lock.sh - File-based locking/semaphore for scripts
#
# Usage:
#   lock.sh <lock_name> <command...>
#   lock.sh deploy ./deploy.sh production
#   lock.sh --timeout 30 build make all
#
# Options:
#   --timeout <sec>   Wait up to N seconds for lock (default: 0 = fail immediately)
#   --stale <sec>     Consider locks older than N seconds stale (default: 3600)
#   --info <name>     Show lock info
#   --release <name>  Force release a lock
#   --list            List all current locks

set -uo pipefail

# Defaults
LOCK_DIR="${CLAUDE_LOCK_DIR:-${TMPDIR:-/tmp}/claude-locks}"
TIMEOUT=0
STALE_THRESHOLD=3600

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$LOCK_DIR"

show_help() {
    cat << 'EOF'
lock.sh - File-based locking/semaphore for scripts

Usage:
  lock.sh [options] <lock_name> <command...>

Options:
  --timeout <sec>   Wait up to N seconds for lock (default: 0 = fail immediately)
  --stale <sec>     Consider locks older than N seconds stale (default: 3600)
  --info <name>     Show information about a lock
  --release <name>  Force release a lock
  --list            List all current locks

Examples:
  # Prevent concurrent deploys
  lock.sh deploy ./deploy.sh production

  # Wait up to 60 seconds for lock
  lock.sh --timeout 60 build make all

  # Check who holds a lock
  lock.sh --info deploy

  # Release a stuck lock
  lock.sh --release deploy

Use cases:
  - Prevent concurrent builds
  - Serialize deploys
  - Protect shared resources
  - Prevent duplicate cron jobs

EOF
    exit 0
}

# Get lock file path
lock_file() {
    echo "$LOCK_DIR/${1}.lock"
}

# Create lock with metadata
create_lock() {
    local name="$1"
    local file=$(lock_file "$name")

    cat > "$file" << EOF
pid=$$
user=$(whoami)
host=$(hostname)
command=$*
created=$(date +%s)
created_human=$(date)
EOF
}

# Check if lock exists and is valid
check_lock() {
    local name="$1"
    local file=$(lock_file "$name")

    [[ ! -f "$file" ]] && return 1

    # Check if stale
    local created=$(grep "^created=" "$file" 2>/dev/null | cut -d= -f2)
    local now=$(date +%s)
    local age=$((now - created))

    if [[ $age -gt $STALE_THRESHOLD ]]; then
        echo -e "${YELLOW}Stale lock detected (${age}s old), removing${NC}" >&2
        rm -f "$file"
        return 1
    fi

    # Check if owning process is still running
    local pid=$(grep "^pid=" "$file" 2>/dev/null | cut -d= -f2)
    if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}Dead lock detected (PID $pid not running), removing${NC}" >&2
        rm -f "$file"
        return 1
    fi

    return 0
}

# Acquire lock
acquire_lock() {
    local name="$1"
    local file=$(lock_file "$name")
    local waited=0

    while true; do
        # Try to create lock atomically
        if ( set -o noclobber; echo "$$" > "$file.tmp" ) 2>/dev/null; then
            mv "$file.tmp" "$file"
            create_lock "$name" "$@"
            return 0
        fi

        # Lock exists - check if valid
        if ! check_lock "$name"; then
            continue  # Lock was stale, try again
        fi

        # Lock is held by someone else
        if [[ $TIMEOUT -eq 0 ]]; then
            return 1
        fi

        if [[ $waited -ge $TIMEOUT ]]; then
            return 1
        fi

        echo -e "${YELLOW}Waiting for lock '$name'...${NC}" >&2
        sleep 1
        ((waited++))
    done
}

# Release lock
release_lock() {
    local name="$1"
    local file=$(lock_file "$name")

    rm -f "$file" "$file.tmp"
}

# Show lock info
show_info() {
    local name="$1"
    local file=$(lock_file "$name")

    if [[ ! -f "$file" ]]; then
        echo "Lock '$name' is not held"
        return 0
    fi

    echo "=== Lock: $name ==="
    cat "$file"

    local created=$(grep "^created=" "$file" | cut -d= -f2)
    local now=$(date +%s)
    local age=$((now - created))
    echo "age=${age}s"
}

# List all locks
list_locks() {
    echo "=== Current Locks ==="
    echo ""

    local found=0
    for f in "$LOCK_DIR"/*.lock; do
        [[ -f "$f" ]] || continue
        local name=$(basename "$f" .lock)

        if check_lock "$name" 2>/dev/null; then
            local pid=$(grep "^pid=" "$f" | cut -d= -f2)
            local user=$(grep "^user=" "$f" | cut -d= -f2)
            local created=$(grep "^created=" "$f" | cut -d= -f2)
            local age=$(( $(date +%s) - created ))

            echo -e "${GREEN}$name${NC}"
            echo "  PID: $pid, User: $user, Age: ${age}s"
            ((found++))
        fi
    done

    if [[ $found -eq 0 ]]; then
        echo "No active locks"
    fi
}

# Parse arguments
LOCK_NAME=""
COMMAND=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --stale)
            STALE_THRESHOLD="$2"
            shift 2
            ;;
        --info)
            show_info "$2"
            exit 0
            ;;
        --release)
            release_lock "$2"
            echo "Lock '$2' released"
            exit 0
            ;;
        --list)
            list_locks
            exit 0
            ;;
        *)
            if [[ -z "$LOCK_NAME" ]]; then
                LOCK_NAME="$1"
            else
                COMMAND+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ -z "$LOCK_NAME" ]]; then
    echo "Error: No lock name specified" >&2
    exit 1
fi

if [[ ${#COMMAND[@]} -eq 0 ]]; then
    echo "Error: No command specified" >&2
    exit 1
fi

# Try to acquire lock
if ! acquire_lock "$LOCK_NAME" "${COMMAND[@]}"; then
    echo -e "${RED}Failed to acquire lock '$LOCK_NAME'${NC}" >&2
    show_info "$LOCK_NAME" >&2
    exit 1
fi

# Ensure lock is released on exit
trap "release_lock '$LOCK_NAME'" EXIT

# Run the command
echo -e "${GREEN}Lock acquired: $LOCK_NAME${NC}" >&2
"${COMMAND[@]}"
exit_code=$?

echo -e "${GREEN}Lock released: $LOCK_NAME${NC}" >&2
exit $exit_code
