#!/usr/bin/env bash
# Offload API calls and compress responses
# Extracts only essential fields from JSON responses
# Usage: offload-api.sh <url> [fields] [--method METHOD] [--header HEADER]
#
# Safer alternative to passing raw curl commands - parses URL and options directly

set -euo pipefail

URL=""
FIELDS=""
METHOD="GET"
HEADERS=()

usage() {
    cat << 'EOF'
offload-api.sh - Fetch API and extract fields

Usage:
  offload-api.sh <url> [fields] [options]

Options:
  --method, -X METHOD    HTTP method (default: GET)
  --header, -H HEADER    Add header (can be repeated)
  --help                 Show this help

Examples:
  offload-api.sh 'https://api.example.com/data' 'id,name,status'
  offload-api.sh 'https://api.github.com/repos/owner/repo' 'name,stars' -H 'Accept: application/json'

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -X|--method) METHOD="$2"; shift 2 ;;
        -H|--header) HEADERS+=("-H" "$2"); shift 2 ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$URL" ]]; then
                URL="$1"
            elif [[ -z "$FIELDS" ]]; then
                FIELDS="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$URL" ]]; then
    echo "Error: URL required" >&2
    usage
fi

# Validate URL format (basic check)
if ! [[ "$URL" =~ ^https?:// ]]; then
    echo "Error: URL must start with http:// or https://" >&2
    exit 1
fi

# Execute curl with parsed arguments (no shell injection possible)
# Handle empty HEADERS array safely with set -u
if [[ ${#HEADERS[@]} -gt 0 ]]; then
    RESPONSE=$(curl -s -X "$METHOD" "${HEADERS[@]}" "$URL" 2>/dev/null)
else
    RESPONSE=$(curl -s -X "$METHOD" "$URL" 2>/dev/null)
fi

if [[ -z "$RESPONSE" ]]; then
    echo "Error: No response from API"
    exit 1
fi

# Get response stats
RESPONSE_SIZE=$(echo "$RESPONSE" | wc -c)

echo "=== API Response Summary ==="
echo "Raw size: $RESPONSE_SIZE bytes"
echo ""

# If fields specified, extract them
if [[ -n "$FIELDS" ]]; then
    IFS=',' read -ra FIELD_ARRAY <<< "$FIELDS"
    JQ_SELECT=""
    for field in "${FIELD_ARRAY[@]}"; do
        field=$(echo "$field" | xargs)
        if [[ -n "$JQ_SELECT" ]]; then
            JQ_SELECT="$JQ_SELECT, "
        fi
        JQ_SELECT="$JQ_SELECT$field: .$field"
    done

    echo "## Extracted fields: $FIELDS"
    echo ""

    if echo "$RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
        ITEM_COUNT=$(echo "$RESPONSE" | jq 'length')
        echo "Items in response: $ITEM_COUNT"
        echo ""
        COMPRESSED=$(echo "$RESPONSE" | jq "[.[] | {$JQ_SELECT}]" 2>/dev/null)
        echo "$COMPRESSED"
        COMPRESSED_SIZE=$(echo "$COMPRESSED" | wc -c)
    else
        COMPRESSED=$(echo "$RESPONSE" | jq "{$JQ_SELECT}" 2>/dev/null)
        echo "$COMPRESSED"
        COMPRESSED_SIZE=$(echo "$COMPRESSED" | wc -c)
    fi

    SAVINGS=$((100 - (COMPRESSED_SIZE * 100 / RESPONSE_SIZE)))
    echo ""
    echo "Compressed size: $COMPRESSED_SIZE bytes (${SAVINGS}% savings)"
else
    # No fields specified, show structure summary
    echo "## Response structure:"
    echo "$RESPONSE" | jq 'if type == "array" then {type: "array", length: length, sample: .[0]} else keys end' 2>/dev/null || echo "$RESPONSE" | head -c 500
fi
