#!/usr/bin/env bash
# smart-yaml.sh - YAML processor using yq
# Usage: smart-yaml.sh <file> [query] [options]
# Supports YAML, XML, TOML via yq

set -e

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

# Find yq
YQ=""
if command -v yq &>/dev/null; then
    YQ="yq"
elif [[ -x "$HOME/.local/bin/yq" ]]; then
    YQ="$HOME/.local/bin/yq"
elif [[ -x /snap/bin/yq ]]; then
    YQ="/snap/bin/yq"
elif [[ -x "$HOME/go/bin/yq" ]]; then
    YQ="$HOME/go/bin/yq"
fi

if [[ -z "$YQ" ]]; then
    echo "Error: yq not found. Install: snap install yq" >&2
    # Fallback: use Python for basic YAML parsing
    # Use environment variable to safely pass filename (no shell injection)
    if command -v python3 &>/dev/null; then
        echo "Falling back to Python yaml module..." >&2
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
