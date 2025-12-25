#!/usr/bin/env bash
# common.sh - Shared library functions for Claude Code scripts
#
# Usage:
#   source ~/.claude/scripts/lib/common.sh
#
# Provides:
#   - Consistent error handling
#   - Logging with levels and colors
#   - Utility functions
#   - Fallback command detection
#   - Token/output formatting

COMMON_SH_VERSION="1.1.0"

# Prevent double-sourcing
[[ -n "${COMMON_SH_LOADED:-}" ]] && return 0
COMMON_SH_LOADED=1

# Colors
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export PURPLE='\033[0;35m'
export CYAN='\033[0;36m'
export NC='\033[0m'

# Logging level (0=silent, 1=error, 2=warn, 3=info, 4=debug)
export LOG_LEVEL="${LOG_LEVEL:-3}"

# Script directory
export CLAUDE_SCRIPTS="${CLAUDE_SCRIPTS:-$HOME/.claude/scripts}"

#
# Logging functions
#

log_error() {
    [[ $LOG_LEVEL -ge 1 ]] && echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_warn() {
    [[ $LOG_LEVEL -ge 2 ]] && echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_info() {
    [[ $LOG_LEVEL -ge 3 ]] && echo -e "${GREEN}[INFO]${NC} $*" >&2
}

log_debug() {
    [[ $LOG_LEVEL -ge 4 ]] && echo -e "${BLUE}[DEBUG]${NC} $*" >&2
}

# Log with custom prefix
log() {
    local prefix="${1:-INFO}"
    shift
    echo -e "[${prefix}] $*" >&2
}

#
# Error handling
#

# Die with error message
die() {
    log_error "$@"
    exit 1
}

# Die if command fails
require() {
    "$@" || die "Command failed: $*"
}

# Set strict mode
strict_mode() {
    set -euo pipefail
    trap 'log_error "Error on line $LINENO. Exit code: $?"' ERR
}

#
# Command detection with fallbacks and caching
#

# Cache for tool lookups (persists for session)
declare -A _TOOL_CACHE 2>/dev/null || true

# Find command with fallbacks (cached)
find_command() {
    local name="$1"
    shift

    # Check cache first
    local cache_key="tool:$name"
    if [[ -n "${_TOOL_CACHE[$cache_key]:-}" ]]; then
        echo "${_TOOL_CACHE[$cache_key]}"
        return 0
    fi

    local result=""

    # Check primary name
    if command -v "$name" &>/dev/null; then
        result="$name"
    # Check in cargo bin
    elif [[ -x "$HOME/.cargo/bin/$name" ]]; then
        result="$HOME/.cargo/bin/$name"
    # Check in go bin
    elif [[ -x "$HOME/go/bin/$name" ]]; then
        result="$HOME/go/bin/$name"
    # Check in local bin
    elif [[ -x "$HOME/.local/bin/$name" ]]; then
        result="$HOME/.local/bin/$name"
    # Check snap bin
    elif [[ -x "/snap/bin/$name" ]]; then
        result="/snap/bin/$name"
    else
        # Check fallbacks
        for fallback in "$@"; do
            if command -v "$fallback" &>/dev/null; then
                result="$fallback"
                break
            fi
        done
    fi

    if [[ -n "$result" ]]; then
        _TOOL_CACHE[$cache_key]="$result"
        echo "$result"
        return 0
    fi

    return 1
}

# Common tool lookups (all cached via find_command)
find_fd() { find_command fd fdfind; }
find_bat() { find_command bat batcat; }
find_rg() { find_command rg; }
find_eza() { find_command eza exa; }
find_delta() { find_command delta; }
find_difft() { find_command difft; }
find_dust() { find_command dust; }
find_sd() { find_command sd; }
find_yq() { find_command yq; }
find_jq() { find_command jq; }
find_htmlq() { find_command htmlq; }
find_gron() { find_command gron; }
find_xh() { find_command xh curlie http curl; }
find_tokei() { find_command tokei; }
find_ast_grep() { find_command ast-grep sg; }
find_fzf() { find_command fzf; }
find_zoxide() { find_command zoxide; }

# Check if tool exists (cached)
has_command() {
    local cache_key="has:$1"
    if [[ -n "${_TOOL_CACHE[$cache_key]:-}" ]]; then
        [[ "${_TOOL_CACHE[$cache_key]}" == "1" ]]
        return $?
    fi

    if command -v "$1" &>/dev/null; then
        _TOOL_CACHE[$cache_key]="1"
        return 0
    else
        _TOOL_CACHE[$cache_key]="0"
        return 1
    fi
}

# Require a command or die
require_command() {
    has_command "$1" || die "Required command not found: $1"
}

# Clear tool cache (useful after installing new tools)
clear_tool_cache() {
    _TOOL_CACHE=()
}

#
# Utility functions
#

# Truncate text to max length
truncate() {
    local max="${1:-80}"
    local text="${2:-$(cat)}"

    if [[ ${#text} -gt $max ]]; then
        echo "${text:0:$((max-3))}..."
    else
        echo "$text"
    fi
}

# Truncate lines to max count
truncate_lines() {
    local max="${1:-20}"
    local input="${2:-$(cat)}"

    local count
    count=$(printf '%s\n' "$input" | wc -l)
    if [[ $count -gt $max ]]; then
        printf '%s\n' "$input" | head -n "$max"
        echo "[... $((count - max)) more lines]"
    else
        printf '%s\n' "$input"
    fi
}

# Format bytes to human readable
format_bytes() {
    local bytes="$1"
    if [[ $bytes -ge 1073741824 ]]; then
        echo "$(( bytes / 1073741824 ))G"
    elif [[ $bytes -ge 1048576 ]]; then
        echo "$(( bytes / 1048576 ))M"
    elif [[ $bytes -ge 1024 ]]; then
        echo "$(( bytes / 1024 ))K"
    else
        echo "${bytes}B"
    fi
}

# Format duration to human readable
format_duration() {
    local seconds="$1"
    if [[ $seconds -ge 3600 ]]; then
        echo "$(( seconds / 3600 ))h $((( seconds % 3600) / 60 ))m"
    elif [[ $seconds -ge 60 ]]; then
        echo "$(( seconds / 60 ))m $(( seconds % 60 ))s"
    else
        echo "${seconds}s"
    fi
}

# Check if running in terminal
is_terminal() {
    [[ -t 1 ]]
}

# Check if CI environment
is_ci() {
    [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" || -n "${JENKINS_URL:-}" ]]
}

#
# Path utilities
#

# Get relative path from current dir
relative_path() {
    local path="$1"
    local cwd="${2:-$(pwd)}"

    # Use realpath if available (preferred, no python dependency)
    if command -v realpath &>/dev/null; then
        realpath --relative-to="$cwd" "$path" 2>/dev/null || echo "$path"
    else
        # Fallback to python if realpath not available
        # Use environment variables to safely pass values (no shell injection)
        PATH_ARG="$path" CWD_ARG="$cwd" python3 -c 'import os; print(os.path.relpath(os.environ["PATH_ARG"], os.environ["CWD_ARG"]))' 2>/dev/null || echo "$path"
    fi
}

# Ensure path exists
ensure_dir() {
    local dir="$1"
    [[ -d "$dir" ]] || mkdir -p "$dir"
}

# Safe temp file
temp_file() {
    local prefix="${1:-claude}"
    mktemp "/tmp/${prefix}.XXXXXX"
}

# Cleanup temp files on exit
cleanup_temps() {
    local pattern="${1:-/tmp/claude.*}"
    trap "rm -f $pattern" EXIT
}

#
# Git utilities
#

# Check if in git repo
is_git_repo() {
    git rev-parse --git-dir &>/dev/null
}

# Get git root
git_root() {
    git rev-parse --show-toplevel 2>/dev/null
}

# Get current branch
git_branch() {
    git branch --show-current 2>/dev/null || git rev-parse --short HEAD 2>/dev/null
}

#
# Language detection
#

# Detect programming language from file extension or directory contents
detect_language() {
    local p="$1"
    if [[ -d "$p" ]]; then
        # Check directory for common file types
        if find "$p" -maxdepth 1 -name "*.py" -print -quit 2>/dev/null | grep -q .; then echo "python"
        elif find "$p" -maxdepth 1 -name "*.ts" -print -quit 2>/dev/null | grep -q .; then echo "typescript"
        elif find "$p" -maxdepth 1 -name "*.js" -print -quit 2>/dev/null | grep -q .; then echo "javascript"
        elif find "$p" -maxdepth 1 -name "*.rs" -print -quit 2>/dev/null | grep -q .; then echo "rust"
        elif find "$p" -maxdepth 1 -name "*.go" -print -quit 2>/dev/null | grep -q .; then echo "go"
        elif find "$p" -maxdepth 1 -name "*.cpp" -print -quit 2>/dev/null | grep -q .; then echo "cpp"
        elif find "$p" -maxdepth 1 -name "*.java" -print -quit 2>/dev/null | grep -q .; then echo "java"
        elif find "$p" -maxdepth 1 -name "*.rb" -print -quit 2>/dev/null | grep -q .; then echo "ruby"
        else echo "unknown"
        fi
    else
        case "$p" in
            *.py) echo "python" ;;
            *.ts|*.tsx) echo "typescript" ;;
            *.js|*.jsx|*.mjs) echo "javascript" ;;
            *.rs) echo "rust" ;;
            *.go) echo "go" ;;
            *.c|*.h) echo "c" ;;
            *.cpp|*.cc|*.cxx|*.hpp|*.hxx) echo "cpp" ;;
            *.java) echo "java" ;;
            *.kt|*.kts) echo "kotlin" ;;
            *.rb) echo "ruby" ;;
            *.sh|*.bash) echo "bash" ;;
            *.qml) echo "qml" ;;
            *.md) echo "markdown" ;;
            *.json) echo "json" ;;
            *.yaml|*.yml) echo "yaml" ;;
            *.log) echo "log" ;;
            *) echo "unknown" ;;
        esac
    fi
}

#
# Output formatting
#

# Print a header
print_header() {
    local title="$1"
    echo ""
    echo -e "${CYAN}=== $title ===${NC}"
    echo ""
}

# Print a section
print_section() {
    local title="$1"
    echo ""
    echo -e "${BLUE}## $title${NC}"
}

# Print a success message
print_success() {
    echo -e "${GREEN}✓${NC} $*"
}

# Print a failure message
print_failure() {
    echo -e "${RED}✗${NC} $*"
}

# Print a warning message
print_warning() {
    echo -e "${YELLOW}!${NC} $*"
}

#
# JSON utilities
#

# Check if jq is available
has_jq() {
    has_command jq
}

# Safe jq with fallback
safe_jq() {
    if has_jq; then
        jq "$@"
    else
        cat  # Pass through if jq not available
    fi
}

# Extract JSON field
json_field() {
    local field="$1"
    safe_jq -r ".$field // empty"
}

#
# Show what's available
#

common_help() {
    cat << EOF
common.sh v$COMMON_SH_VERSION - Shared library for Claude Code scripts

Logging:
  log_error, log_warn, log_info, log_debug
  die "message"          Exit with error
  strict_mode            Enable set -euo pipefail with trap

Commands:
  has_command <name>     Check if command exists
  require_command <name> Die if command missing
  find_fd, find_bat, find_rg, find_eza, find_delta
  find_yq, find_htmlq, find_gron, find_sd

Formatting:
  truncate <max> "text"       Truncate text
  truncate_lines <max>        Truncate stdin
  format_bytes <n>            Human readable bytes
  format_duration <sec>       Human readable duration

Output:
  print_header, print_section
  print_success, print_failure, print_warning

Git:
  is_git_repo, git_root, git_branch

Utilities:
  is_terminal, is_ci
  temp_file [prefix]
  ensure_dir <path>
  relative_path <path> [base]

Usage:
  source ~/.claude/scripts/lib/common.sh

EOF
}

# Export all functions
export -f log_error log_warn log_info log_debug log die require strict_mode
export -f find_command find_fd find_bat find_rg find_eza find_delta find_yq find_htmlq find_gron find_sd
export -f has_command require_command
export -f truncate truncate_lines format_bytes format_duration
export -f is_terminal is_ci relative_path ensure_dir temp_file cleanup_temps
export -f is_git_repo git_root git_branch detect_language
export -f print_header print_section print_success print_failure print_warning
export -f has_jq safe_jq json_field common_help
