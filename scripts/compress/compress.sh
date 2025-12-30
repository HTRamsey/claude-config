#!/usr/bin/env bash
# compress.sh - Unified compression for various output types
#
# Usage:
#   compress.sh --type diff HEAD~3
#   compress.sh --type build < build.log
#   compress.sh --type tests < test-output.log
#   compress.sh --type stack < error.log
#   compress.sh --type logs '<logs>' [max_lines]
#   compress.sh --type json '<json>' 'field1,field2'
#   compress.sh --type list '<list>' '<pattern>' [limit]
#   compress.sh --type errors < errors.log
#
# JSON output for pipeline integration:
#   compress.sh --type diff --json HEAD~3
#
# Short form:
#   compress.sh -t diff -j HEAD~3

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

SCRIPT_VERSION="1.1.0"

# Default settings
MAX_LINES=${MAX_LINES:-50}
MAX_SAMPLE=${MAX_SAMPLE:-5}
MAX_FILES=${MAX_FILES:-20}
JSON_OUTPUT=false

usage() {
    cat << 'EOF'
Usage: compress.sh --type TYPE [options] [args...]

Types:
  diff [ref]           Git diff compression (default: staged/unstaged)
  build [file]         Build output - errors and warnings only
  tests [file]         Test output - failures only (pytest/jest/cargo/go)
  stack [file]         Stack trace - app frames only
  logs '<text>' [max]  Log output - errors/warnings only
  json '<json>' 'f,f'  JSON - extract specific fields
  list '<list>' 'pat'  List - filter and limit
  errors [file]        Deduplicate repeated errors

Options:
  -t, --type TYPE      Compression type (required)
  -j, --json           Output as JSON (for pipeline integration)
  -h, --help           Show this help
  --version            Show version

Examples:
  compress.sh -t diff HEAD~3
  make 2>&1 | compress.sh -t build
  pytest -v 2>&1 | compress.sh -t tests
  cat error.log | compress.sh -t stack

  # JSON output for automation
  compress.sh -t diff --json HEAD~3 | jq '.files'
  compress.sh -t build --json < build.log | jq '.status'
EOF
    exit 0
}

# JSON escape helper
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    echo "$s"
}

# JSON array from lines
json_array() {
    local first=true
    echo -n "["
    while IFS= read -r line; do
        $first || echo -n ","
        first=false
        echo -n "\"$(json_escape "$line")\""
    done
    echo "]"
}

# ============================================================
# DIFF COMPRESSION
# ============================================================
compress_diff() {
    local ref="${1:-}"
    local diff_input

    if [[ "$ref" == "-" ]]; then
        diff_input=$(cat)
    elif [[ -n "$ref" ]]; then
        diff_input=$(git diff "$ref" 2>/dev/null || git show "$ref" --format="" 2>/dev/null)
    else
        diff_input=$(git diff --cached 2>/dev/null)
        [[ -z "$diff_input" ]] && diff_input=$(git diff 2>/dev/null)
    fi

    if [[ -z "$diff_input" ]]; then
        if $JSON_OUTPUT; then
            echo '{"status":"empty","message":"No diff found","files":[]}'
        else
            echo "No diff found"
        fi
        return 0
    fi

    local total_lines=$(echo "$diff_input" | wc -l)
    local added=$(echo "$diff_input" | grep -c "^+" || echo 0)
    local removed=$(echo "$diff_input" | grep -c "^-" || echo 0)
    local file_count=$(echo "$diff_input" | grep -c "^diff --git" || echo 0)

    if $JSON_OUTPUT; then
        # Build JSON output
        local files_json=$(echo "$diff_input" | awk '
        BEGIN { first=1 }
        /^diff --git/ {
            if (file != "") {
                if (!first) printf ","
                first=0
                printf "{\"file\":\"%s\",\"added\":%d,\"removed\":%d}", file, a, r
            }
            file = $NF; gsub(/^b\//, "", file); a = 0; r = 0
        }
        /^\+[^+]/ { a++ }
        /^-[^-]/ { r++ }
        END {
            if (file != "") {
                if (!first) printf ","
                printf "{\"file\":\"%s\",\"added\":%d,\"removed\":%d}", file, a, r
            }
        }
        ')

        local sig_changes=$(echo "$diff_input" | grep -E "^[\+\-].*(function|class|def |const |let |var |export |import |struct |impl |fn )" | head -$MAX_SAMPLE | json_array)

        cat << EOF
{"type":"diff","summary":{"total_lines":$total_lines,"added":$added,"removed":$removed,"file_count":$file_count},"files":[$files_json],"significant_changes":$sig_changes}
EOF
    else
        echo "=== DIFF SUMMARY ==="
        echo "Total lines: $total_lines | Added: $added | Removed: $removed"
        echo ""
        echo "=== FILES CHANGED ==="

        echo "$diff_input" | awk '
        /^diff --git/ {
            if (file != "") printf "%-50s +%-4d -%-4d\n", file, a, r
            file = $NF; gsub(/^b\//, "", file); a = 0; r = 0
        }
        /^\+[^+]/ { a++ }
        /^-[^-]/ { r++ }
        END { if (file != "") printf "%-50s +%-4d -%-4d\n", file, a, r }
        ' | head -$MAX_FILES

        [[ $file_count -gt $MAX_FILES ]] && echo "... and $((file_count - MAX_FILES)) more files"

        echo ""
        echo "=== SIGNIFICANT CHANGES (sample) ==="
        echo "$diff_input" | grep -E "^[\+\-].*(function|class|def |const |let |var |export |import |struct |impl |fn )" | head -$MAX_SAMPLE
        echo ""
        echo "[Compressed from $total_lines lines]"
    fi
}

# ============================================================
# BUILD COMPRESSION
# ============================================================
compress_build() {
    local input
    if [[ -f "${1:-}" ]]; then
        input=$(cat "$1")
    else
        input=$(cat)
    fi

    local total_lines=$(echo "$input" | wc -l | tr -d ' ')
    local errors=$(echo "$input" | grep -iE "error|fatal|failed|undefined reference|cannot find|no such file" | grep -v "warning" | head -50 || true)
    local error_count=$(echo "$errors" | grep -c . || echo 0)
    local warning_count=$(echo "$input" | grep -ci "warning:" || echo 0)

    local status="unclear"
    if echo "$input" | grep -qi "build successful\|built successfully\|compilation finished\|\[100%\]"; then
        status="success"
    elif [[ $error_count -gt 0 ]]; then
        status="failed"
    fi

    if $JSON_OUTPUT; then
        local errors_json=$(echo "$errors" | head -30 | json_array)
        local warnings_json=$(echo "$input" | grep -i "warning:" | head -20 | json_array)
        local last_lines=$(echo "$input" | tail -5 | json_array)

        cat << EOF
{"type":"build","summary":{"total_lines":$total_lines,"error_count":$error_count,"warning_count":$warning_count},"status":"$status","errors":$errors_json,"warnings":$warnings_json,"last_lines":$last_lines}
EOF
    else
        echo "=== Build Summary (from $total_lines lines) ==="
        echo ""

        if [[ $error_count -gt 0 ]]; then
            echo "## ERRORS ($error_count):"
            echo "$errors" | head -30
            [[ $error_count -gt 30 ]] && echo "... and $((error_count - 30)) more errors"
            echo ""
        fi

        if [[ $warning_count -gt 0 ]]; then
            echo "## WARNINGS ($warning_count total, showing first 20):"
            echo "$input" | grep -i "warning:" | head -20
            echo ""
        fi

        case "$status" in
            success) echo "## STATUS: Build appears SUCCESSFUL" ;;
            failed)  echo "## STATUS: Build FAILED with $error_count error(s)" ;;
            *)       echo "## STATUS: Build result unclear" ;;
        esac

        echo ""
        echo "## Last 5 lines:"
        echo "$input" | tail -5
    fi
}

# ============================================================
# TEST COMPRESSION
# ============================================================
compress_tests() {
    local input
    if [[ -n "${1:-}" && -f "$1" ]]; then
        input=$(cat "$1")
    else
        input=$(cat)
    fi

    local total_lines=$(echo "$input" | wc -l)

    # Detect test framework once (single pass with awk for efficiency)
    local framework
    framework=$(echo "$input" | awk '
        /FAILED|PASSED|pytest|=====/ { print "pytest"; exit }
        /FAIL |PASS |✓|✕|expect\(|describe\(/ { print "jest"; exit }
        /test .* \.\.\. (ok|FAILED)|running [0-9]+ tests/ { print "cargo"; exit }
        /--- FAIL|--- PASS|=== RUN/ { print "go"; exit }
        END { if (!printed) print "generic" }
    ')

    case "$framework" in
        pytest)
            echo "=== PYTEST FAILURES ==="
            echo "$input" | grep -E "(FAILED|ERROR|::.*FAILED)" | head -50
            echo ""
            echo "=== ERROR DETAILS ==="
            echo "$input" | awk '/^E       |^>       |AssertionError|assert |FAILED/{print}' | head -100
            echo ""
            echo "=== SUMMARY ==="
            echo "$input" | grep -E "^(FAILED|PASSED|ERROR|=====.*=====)" | tail -10
            ;;
        jest)
            echo "=== JEST/MOCHA FAILURES ==="
            echo "$input" | awk '/FAIL |✕|Error:|expect\(.*\)\./{found=1} found{print; if(/^$/) found=0}' | head -100
            echo ""
            echo "=== SUMMARY ==="
            echo "$input" | grep -E "(Tests:|Test Suites:|FAIL |PASS )" | tail -10
            ;;
        cargo)
            echo "=== CARGO TEST FAILURES ==="
            echo "$input" | grep -E "FAILED|panicked|^thread .* panicked" | head -50
            echo ""
            echo "=== SUMMARY ==="
            echo "$input" | grep -E "^test result:|failures:" | tail -10
            ;;
        go)
            echo "=== GO TEST FAILURES ==="
            echo "$input" | awk '/--- FAIL/,/--- (PASS|FAIL)|^FAIL/{print}' | head -100
            echo ""
            echo "=== SUMMARY ==="
            echo "$input" | grep -E "^(FAIL|PASS|ok)\s" | tail -10
            ;;
        *)
            echo "=== TEST OUTPUT (filtered) ==="
            echo "$input" | grep -iE "(fail|error|exception|assert|expected|actual)" | head -100
            ;;
    esac

    echo ""
    echo "[Compressed from $total_lines lines]"
}

# ============================================================
# STACK TRACE COMPRESSION
# ============================================================
compress_stack() {
    local input
    if [[ -f "$1" ]]; then
        input=$(cat "$1")
    else
        input=$(cat)
    fi

    local total_lines=$(echo "$input" | wc -l)
    local noise="node_modules|vendor/|site-packages|\.cargo|/usr/lib|/usr/local|internal/|__pycache__|java\.(lang|util|io)\.|sun\.|react-dom|webpack"

    echo "=== ERROR MESSAGE ==="
    echo "$input" | awk '
    /^[A-Za-z]*Error:|^Exception|^Traceback|^panic:|^fatal:|^error\[|^thread.*panicked/ { found=1 }
    found { print; if (/^    at |^  File |^  at |^\s+\d+:/) exit }
    ' | head -10

    echo ""
    echo "=== RELEVANT STACK FRAMES ==="
    echo "$input" | awk -v noise="$noise" '
    /^    at |^  File |^  at |^\s+at |^#[0-9]+|^\s+\d+: / {
        if (match($0, noise)) { skipped++; next }
        if (match($0, "(src/|app/|lib/|test/|components/)") || frame++ < 3) print
        else skipped++
        next
    }
    /Error|Exception|panic|assert/ { print }
    END { if (skipped > 0) printf "\n[... %d framework frames filtered ...]\n", skipped }
    '

    echo ""
    echo "[Compressed from $total_lines lines]"
}

# ============================================================
# LOG COMPRESSION
# ============================================================
compress_logs() {
    local input="$1"
    local max="${2:-$MAX_LINES}"

    if [[ -z "$input" ]]; then
        input=$(cat)
    fi

    local total_lines=$(echo "$input" | wc -l)
    local error_count=$(echo "$input" | grep -ciE '(error|fatal|exception|failed)' || echo 0)
    local warn_count=$(echo "$input" | grep -ciE '(warn|warning)' || echo 0)

    echo "=== Log Summary ==="
    echo "Total: $total_lines | Errors: $error_count | Warnings: $warn_count"
    echo ""

    if [[ $error_count -gt 0 ]]; then
        echo "=== Errors ==="
        echo "$input" | grep -iE '(error|fatal|exception|failed)' | head -n "$max"
        echo ""
    fi

    if [[ $warn_count -gt 0 ]] && [[ $error_count -lt $max ]]; then
        echo "=== Warnings ==="
        echo "$input" | grep -iE '(warn|warning)' | head -n $((max - error_count))
        echo ""
    fi

    echo "=== Last 10 lines ==="
    echo "$input" | tail -n 10
}

# ============================================================
# JSON COMPRESSION
# ============================================================
compress_json() {
    local json="$1"
    local fields="$2"

    if [[ "$json" == "-" ]]; then
        json=$(cat)
    fi

    if [[ -z "$json" ]] || [[ -z "$fields" ]]; then
        echo "Usage: compress.sh -t json '<json>' 'field1,field2'"
        return 1
    fi

    IFS=',' read -ra field_array <<< "$fields"
    local jq_select=""
    for f in "${field_array[@]}"; do
        f=$(echo "$f" | xargs)
        [[ -n "$jq_select" ]] && jq_select="$jq_select, "
        jq_select="$jq_select$f: .$f"
    done

    if echo "$json" | jq -e 'type == "array"' > /dev/null 2>&1; then
        echo "$json" | jq "[.[] | {$jq_select}]" 2>/dev/null || echo "$json" | head -c 2000
    else
        echo "$json" | jq "{$jq_select}" 2>/dev/null || echo "$json" | head -c 2000
    fi
}

# ============================================================
# LIST COMPRESSION
# ============================================================
compress_list() {
    local input="$1"
    local filter="${2:-.*}"
    local limit="${3:-20}"

    if [[ -z "$input" ]]; then
        input=$(cat)
    fi

    if echo "$input" | jq -e 'type == "array"' > /dev/null 2>&1; then
        local total=$(echo "$input" | jq 'length')
        echo "=== List Summary ==="
        echo "Total items: $total | Showing: first $limit matching '$filter'"
        echo ""
        if [[ "$filter" == ".*" ]]; then
            echo "$input" | jq ".[:$limit]"
        else
            echo "$input" | jq "[.[] | select(. | tostring | test(\"$filter\"; \"i\"))][:$limit]"
        fi
    else
        local total=$(echo "$input" | wc -l)
        local matched=$(echo "$input" | grep -cE "$filter" || echo 0)
        echo "=== List Summary ==="
        echo "Total: $total | Matched '$filter': $matched | Showing: first $limit"
        echo ""
        echo "$input" | grep -E "$filter" | head -n "$limit"
    fi
}

# ============================================================
# ERROR DEDUPLICATION
# ============================================================
compress_errors() {
    local input
    if [[ -f "$1" ]]; then
        input=$(cat "$1")
    else
        input=$(cat)
    fi

    local total_lines=$(echo "$input" | wc -l)

    echo "=== UNIQUE ERRORS (with counts) ==="
    echo "$input" | grep -iE "(error|fail|exception|fatal|panic|warning)" | \
        sed -E '
            s/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]*/[TIME]/g
            s/0x[0-9a-fA-F]+/[ADDR]/g
            s/:[0-9]+:/:N:/g
            s/line [0-9]+/line N/gi
        ' | sort | uniq -c | sort -rn | head -50 | \
        awk '{ printf "%4dx  %s\n", $1, substr($0, index($0,$2)) }'

    echo ""
    echo "=== SUMMARY ==="
    local errors=$(echo "$input" | grep -ciE "\berror\b" || echo 0)
    local warnings=$(echo "$input" | grep -ci "warning" || echo 0)
    local fatals=$(echo "$input" | grep -ciE "(fatal|panic)" || echo 0)
    echo "Fatal/Panic: $fatals | Errors: $errors | Warnings: $warnings"

    echo ""
    echo "=== ERROR TYPES ==="
    echo "$input" | grep -oiE "[A-Za-z]+Error|[A-Za-z]+Exception" | sort | uniq -c | sort -rn | head -10

    local unique=$(echo "$input" | grep -iE "(error|fail|exception)" | sort -u | wc -l)
    local total_err=$(echo "$input" | grep -ciE "(error|fail|exception)" || echo 0)
    echo ""
    echo "[Found $unique unique patterns from $total_err occurrences in $total_lines lines]"
}

# ============================================================
# MAIN
# ============================================================

TYPE=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--type)
            TYPE="$2"
            shift 2
            ;;
        -j|--json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        --version)
            echo "compress.sh version $SCRIPT_VERSION"
            exit 0
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -z "$TYPE" ]]; then
    echo "Error: --type is required"
    echo "Run 'compress.sh --help' for usage"
    exit 1
fi

case "$TYPE" in
    diff)       compress_diff "${ARGS[@]:-}" ;;
    build)      compress_build "${ARGS[@]:-}" ;;
    tests|test) compress_tests "${ARGS[@]:-}" ;;
    stack|stacktrace) compress_stack "${ARGS[@]:-}" ;;
    logs|log)   compress_logs "${ARGS[@]:-}" ;;
    json)       compress_json "${ARGS[@]:-}" ;;
    list)       compress_list "${ARGS[@]:-}" ;;
    errors|dedup) compress_errors "${ARGS[@]:-}" ;;
    *)
        echo "Unknown type: $TYPE"
        echo "Valid types: diff, build, tests, stack, logs, json, list, errors"
        exit 1
        ;;
esac
