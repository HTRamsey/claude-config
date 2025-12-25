#!/usr/bin/env bash
# smart-json.sh - Token-efficient JSON extraction using jq
# Usage: smart-json.sh <json-source> [fields|jq-filter] [options]
#
# Features:
# - Auto-detects file vs stdin vs raw JSON string
# - Extracts specific fields with simple syntax
# - Compact output by default
# - Handles common patterns easily

set -euo pipefail

source="$1"
filter="${2:-.}"
options="${3:-}"

show_help() {
    cat << 'EOF'
Usage: smart-json.sh <json-source> [fields|jq-filter] [options]

Arguments:
  json-source   File path, JSON string, or "-" for stdin
  fields        Comma-separated field names OR jq filter expression
  options       Additional options: compact, keys, length, type

Examples:
  # Extract from file
  smart-json.sh config.json '.database.host'
  smart-json.sh response.json 'name,email,id'

  # Extract from string
  smart-json.sh '{"a":1,"b":2}' 'a,b'

  # From pipe
  curl -s api.example.com | smart-json.sh - 'data.users[].name'

  # Special options
  smart-json.sh data.json '' keys      # List all keys
  smart-json.sh data.json '' length    # Count items
  smart-json.sh data.json '.items' length  # Count items in array

Field syntax (comma-separated):
  'name'              -> {name: .name}
  'name,email'        -> {name: .name, email: .email}
  'user.name,user.id' -> {name: .user.name, id: .user.id}

EOF
    exit 0
}

[[ "$source" == "-h" || "$source" == "--help" ]] && show_help

if [[ -z "$source" ]]; then
    echo "Usage: smart-json.sh <json-source> [fields|jq-filter]"
    echo "Run with -h for help"
    exit 1
fi

# Determine input source
get_json() {
    if [[ "$source" == "-" ]]; then
        cat
    elif [[ -f "$source" ]]; then
        cat "$source"
    elif [[ "$source" == "{"* || "$source" == "["* ]]; then
        echo "$source"
    else
        echo "Error: Cannot read JSON from: $source" >&2
        exit 1
    fi
}

# Handle special options
case "$options" in
    keys)
        get_json | jq -r "$filter | keys[]?" 2>/dev/null || get_json | jq -r 'keys[]'
        exit 0
        ;;
    length)
        get_json | jq "$filter | length"
        exit 0
        ;;
    type)
        get_json | jq "$filter | type"
        exit 0
        ;;
    compact)
        get_json | jq -c "$filter"
        exit 0
        ;;
esac

# Check if filter is a jq expression or field list
if [[ "$filter" == "."* || "$filter" == "["* || "$filter" == "{" || "$filter" == "|"* ]]; then
    # It's a jq filter expression
    get_json | jq -r "$filter" 2>/dev/null || get_json | jq "$filter"
else
    # It's a comma-separated field list - convert to jq object extraction
    if [[ "$filter" == *","* ]]; then
        # Multiple fields - build jq object
        jq_filter="{"
        first=true
        IFS=',' read -ra fields <<< "$filter"
        for field in "${fields[@]}"; do
            field=$(echo "$field" | xargs)  # trim whitespace
            # Get short name (last part after .)
            short_name="${field##*.}"
            if [[ "$first" == true ]]; then
                first=false
            else
                jq_filter+=", "
            fi
            jq_filter+="\"$short_name\": .$field"
        done
        jq_filter+="}"
        get_json | jq "$jq_filter"
    elif [[ -n "$filter" ]]; then
        # Single field
        get_json | jq -r ".$filter // .$filter"
    else
        # No filter - pretty print with compact arrays
        get_json | jq '.'
    fi
fi
