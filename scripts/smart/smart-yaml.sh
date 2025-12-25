#!/usr/bin/env bash
# smart-yaml.sh - YAML processor using yq
# Usage: smart-yaml.sh <file> [query] [options]
# Supports YAML, XML, TOML via yq

set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

file="${1:-}"
query="${2:-.}"

if [[ -z "$file" ]]; then
    echo "Usage: smart-yaml.sh <file> [query]"
    echo "Examples:"
    echo "  smart-yaml.sh config.yml                    # Pretty print"
    echo "  smart-yaml.sh config.yml '.services'        # Query path"
    echo "  smart-yaml.sh docker-compose.yml '.services | keys'"
    echo "  smart-yaml.sh config.xml -p=xml             # XML input"
    exit 0
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
