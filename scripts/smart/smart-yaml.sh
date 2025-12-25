#!/usr/bin/env bash
# smart-yaml.sh - YAML processor using yq
# Usage: smart-yaml.sh <file> [query] [options]
# Supports YAML, XML, TOML via yq

set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

usage() {
    echo "Usage: $(basename "$0") <file> [query] [options]"
    echo ""
    echo "YAML processor using yq (supports YAML, XML, TOML)"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Arguments:"
    echo "  file          YAML/XML/TOML file to process"
    echo "  query         yq query expression (default: .)"
    echo "  options       Additional yq options (passed through)"
    echo ""
    echo "Features:"
    echo "  - Uses yq for YAML/XML/TOML processing"
    echo "  - Falls back to Python yaml module if yq not available"
    echo "  - Supports jq-like query syntax"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") config.yml                    # Pretty print"
    echo "  $(basename "$0") config.yml '.services'        # Query path"
    echo "  $(basename "$0") docker-compose.yml '.services | keys'"
    echo "  $(basename "$0") config.xml -p=xml             # XML input"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

file="${1:-}"
query="${2:-.}"

if [[ -z "$file" ]]; then
    usage
    exit 1
fi

# Find yq using common.sh
YQ=$(find_yq) || YQ=""

if [[ -z "$YQ" ]]; then
    log_warn "yq not found. Install: snap install yq"
    # Fallback: use Python for basic YAML parsing
    if has_command python3; then
        log_info "Falling back to Python yaml module..."
        INPUT_FILE="$file" python3 -c '
import yaml, os
with open(os.environ["INPUT_FILE"]) as f:
    print(yaml.safe_dump(yaml.safe_load(f)))
'
        exit $?
    fi
    exit 1
fi

# Handle additional args (pass through to yq)
shift 2 2>/dev/null || shift 1 2>/dev/null || true

exec $YQ "$query" "$file" "$@"
