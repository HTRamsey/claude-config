#!/usr/bin/env bash
# smart-http.sh - HTTP client with tiered fallbacks and field extraction
# Usage: smart-http.sh [METHOD] <URL> [--fields field1,field2] [options...]
# Fallback chain: xh → curlie → httpie → curl
#
# Options:
#   --fields, -f FIELDS   Extract specific JSON fields (comma-separated)
#
# Examples:
#   smart-http.sh GET https://api.example.com/users
#   smart-http.sh https://api.github.com/repos/owner/repo --fields name,stars
#   smart-http.sh POST https://api.example.com/users name=john

set -e

# Parse --fields option
FIELDS=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --fields|-f)
            FIELDS="$2"
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done
set -- "${ARGS[@]}"

# Find best available HTTP client
HTTP_CLIENT=""
if command -v xh &>/dev/null; then
    HTTP_CLIENT="xh"
elif [[ -x "$HOME/.cargo/bin/xh" ]]; then
    HTTP_CLIENT="$HOME/.cargo/bin/xh"
elif command -v curlie &>/dev/null; then
    HTTP_CLIENT="curlie"
elif [[ -x "$HOME/go/bin/curlie" ]]; then
    HTTP_CLIENT="$HOME/go/bin/curlie"
elif command -v http &>/dev/null; then
    HTTP_CLIENT="http"  # httpie
elif command -v curl &>/dev/null; then
    HTTP_CLIENT="curl"
else
    echo "Error: No HTTP client found. Install xh: cargo install xh" >&2
    exit 1
fi

# If no args, show usage
if [[ $# -eq 0 ]]; then
    echo "Using: $HTTP_CLIENT"
    echo "Usage: smart-http.sh [METHOD] <URL> [--fields field1,field2] [options...]"
    echo "Examples:"
    echo "  smart-http.sh GET https://api.example.com/users"
    echo "  smart-http.sh https://api.github.com/repos/org/repo --fields name,stargazers_count"
    echo "  smart-http.sh POST https://api.example.com/users name=john"
    exit 0
fi

# Function to extract fields from JSON
extract_fields() {
    local response="$1"
    local fields="$2"

    if [[ -z "$fields" ]]; then
        echo "$response"
        return
    fi

    # Build jq select expression
    IFS=',' read -ra FIELD_ARRAY <<< "$fields"
    JQ_SELECT=""
    for field in "${FIELD_ARRAY[@]}"; do
        field=$(echo "$field" | xargs)
        [[ -n "$JQ_SELECT" ]] && JQ_SELECT="$JQ_SELECT, "
        JQ_SELECT="$JQ_SELECT$field: .$field"
    done

    # Handle arrays vs objects
    if echo "$response" | jq -e 'type == "array"' > /dev/null 2>&1; then
        echo "$response" | jq "[.[] | {$JQ_SELECT}]" 2>/dev/null
    else
        echo "$response" | jq "{$JQ_SELECT}" 2>/dev/null
    fi
}

# Execute request and optionally extract fields
execute_request() {
    local response
    case "$HTTP_CLIENT" in
        xh|*/xh)
            response=$($HTTP_CLIENT "$@" 2>/dev/null)
            ;;
        curlie)
            response=$(curlie "$@" 2>/dev/null)
            ;;
        http)
            response=$(http "$@" 2>/dev/null)
            ;;
        curl)
            # curl needs different syntax
            local method="GET"
            local url=""
            for arg in "$@"; do
                case "$arg" in
                    GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) method="$arg" ;;
                    http://*|https://*) url="$arg" ;;
                esac
            done
            if [[ -n "$url" ]]; then
                response=$(curl -s -X "$method" "$url" 2>/dev/null)
            else
                response=$(curl -s "$@" 2>/dev/null)
            fi
            ;;
    esac

    if [[ -n "$FIELDS" ]]; then
        extract_fields "$response" "$FIELDS"
    else
        echo "$response" | head -100
    fi
}

execute_request "$@"
