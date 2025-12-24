#!/usr/bin/env bash
# smart-http.sh - HTTP client with tiered fallbacks
# Usage: smart-http.sh [METHOD] <URL> [options...]
# Fallback chain: xh → curlie → httpie → curl

set -e

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

# If no args, show which client is being used
if [[ $# -eq 0 ]]; then
    echo "Using: $HTTP_CLIENT"
    echo "Usage: smart-http.sh [METHOD] <URL> [options...]"
    echo "Examples:"
    echo "  smart-http.sh GET https://api.example.com/users"
    echo "  smart-http.sh POST https://api.example.com/users name=john"
    echo "  smart-http.sh https://api.example.com  # defaults to GET"
    exit 0
fi

# Execute with the best available client
case "$HTTP_CLIENT" in
    xh|*/xh)
        exec $HTTP_CLIENT "$@"
        ;;
    curlie)
        exec curlie "$@"
        ;;
    http)
        exec http "$@"
        ;;
    curl)
        # curl needs different syntax, provide basic compatibility
        method="GET"
        url=""
        for arg in "$@"; do
            case "$arg" in
                GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)
                    method="$arg"
                    ;;
                http://*|https://*)
                    url="$arg"
                    ;;
            esac
        done
        if [[ -n "$url" ]]; then
            exec curl -s -X "$method" "$url" | head -100
        else
            exec curl "$@"
        fi
        ;;
esac
