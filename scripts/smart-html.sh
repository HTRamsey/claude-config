#!/usr/bin/env bash
# smart-html.sh - HTML processor using htmlq (CSS selectors)
# Usage: smart-html.sh <file|-> <selector> [options]
# Like jq but for HTML

set -e

input="${1:-}"
selector="${2:-}"

if [[ -z "$input" ]] || [[ -z "$selector" ]]; then
    echo "Usage: smart-html.sh <file|url|-> <selector> [options]"
    echo "Examples:"
    echo "  smart-html.sh page.html 'title'                    # Get title text"
    echo "  smart-html.sh page.html 'a' --attribute href       # Get all link hrefs"
    echo "  smart-html.sh page.html '.content p'               # CSS selector"
    echo "  smart-html.sh page.html 'meta[name=description]' --attribute content"
    echo "  curl -s URL | smart-html.sh - 'h1'                 # From stdin"
    echo "  smart-html.sh https://example.com 'title'          # Fetch and parse"
    exit 0
fi

# Find htmlq
HTMLQ=""
if command -v htmlq &>/dev/null; then
    HTMLQ="htmlq"
elif [[ -x "$HOME/.cargo/bin/htmlq" ]]; then
    HTMLQ="$HOME/.cargo/bin/htmlq"
fi

if [[ -z "$HTMLQ" ]]; then
    echo "Error: htmlq not found. Install: cargo install htmlq" >&2
    # Fallback: use Python with beautifulsoup if available
    if python3 -c "import bs4" 2>/dev/null; then
        echo "Falling back to BeautifulSoup..." >&2
        if [[ "$input" == "-" ]]; then
            python3 -c "from bs4 import BeautifulSoup; import sys; soup = BeautifulSoup(sys.stdin.read(), 'html.parser'); [print(e.get_text()) for e in soup.select('$selector')]"
        else
            python3 -c "from bs4 import BeautifulSoup; soup = BeautifulSoup(open('$input').read(), 'html.parser'); [print(e.get_text()) for e in soup.select('$selector')]"
        fi
        exit $?
    fi
    exit 1
fi

# Handle additional args (pass through to htmlq)
shift 2 2>/dev/null || true

# Handle URL input
if [[ "$input" =~ ^https?:// ]]; then
    curl -s "$input" | $HTMLQ "$selector" "$@"
elif [[ "$input" == "-" ]]; then
    $HTMLQ "$selector" "$@"
else
    cat "$input" | $HTMLQ "$selector" "$@"
fi
