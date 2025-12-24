#!/usr/bin/env bash
# Offload API calls and compress responses
# Extracts only essential fields from JSON responses
# Usage: offload-api.sh '<curl_command>' 'field1,field2'

CURL_CMD="$1"
FIELDS="$2"

if [[ -z "$CURL_CMD" ]]; then
    echo "Usage: offload-api.sh '<curl_command>' 'field1,field2'"
    echo "Example: offload-api.sh 'curl -s https://api.example.com/data' 'id,name,status'"
    exit 1
fi

# Security: Validate command starts with curl/wget and doesn't contain dangerous patterns
if ! [[ "$CURL_CMD" =~ ^(curl|wget)[[:space:]] ]]; then
    echo "Error: Command must start with 'curl' or 'wget'" >&2
    exit 1
fi

# Block command chaining and injection patterns
if [[ "$CURL_CMD" =~ [\;\|\&\$\`] ]] || [[ "$CURL_CMD" =~ \$\( ]]; then
    echo "Error: Command contains prohibited characters (;|&\$\`)" >&2
    exit 1
fi

# Execute using bash -c instead of eval for slightly better isolation
RESPONSE=$(bash -c "$CURL_CMD" 2>/dev/null)

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
