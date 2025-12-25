#!/usr/bin/env bash
# extract-signatures.sh - Extract function/class signatures without implementation
#
# Usage:
#   extract-signatures.sh file.py
#   extract-signatures.sh src/*.ts
#   extract-signatures.sh --lang python file.py
#
# Extracts: Function signatures, class definitions, type definitions, exports
# Removes: Function bodies, implementation details
# Saves: 80-95% tokens while preserving API structure

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

LANG=""
FILES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --lang|-l)
            LANG="$2"
            shift 2
            ;;
        *)
            FILES+=("$1")
            shift
            ;;
    esac
done

if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "Usage: extract-signatures.sh [--lang LANG] file1 [file2 ...]"
    echo "Supported: python, typescript, javascript, go, rust, java, c, cpp"
    exit 1
fi

extract_python() {
    awk '
    /^class / { print; in_class=1; next }
    /^def / { print; next }
    /^    def / && in_class { print; next }
    /^async def / { print; next }
    /^    async def / && in_class { print; next }
    /^@/ { print; next }
    /^[A-Z_]+\s*=/ { print; next }
    /^from .* import|^import / { print; next }
    /^"""/ && !in_docstring { in_docstring=1; print; next }
    in_docstring { print; if (/"""$/) in_docstring=0; next }
    /^[a-zA-Z_][a-zA-Z0-9_]*:.*=/ { print; next }
    ' "$1"
}

extract_typescript() {
    awk '
    /^export |^interface |^type |^class |^enum |^const [A-Z]|^function |^async function / {
        print
        if (/{$/) { depth=1; while(depth>0 && (getline line)>0) { if(line~/{/) depth++; if(line~/}/) depth-- } }
        next
    }
    /^  (public|private|protected|static|async|readonly)? *(get |set )?[a-zA-Z_]+.*\(/ {
        gsub(/{.*/, "{...}")
        print
        next
    }
    /^import |^export \* from|^export {/ { print; next }
    /^\/\*\*/ { in_doc=1 }
    in_doc { print; if (/\*\//) in_doc=0; next }
    ' "$1"
}

extract_go() {
    awk '
    /^package / { print; next }
    /^import / { print; if (/{/) while((getline)>0 && !/}/) print; next }
    /^type .* struct|^type .* interface/ {
        print
        if (/{/) { depth=1; while(depth>0 && (getline)>0) { print; if(/{/) depth++; if(/}/) depth-- } }
        next
    }
    /^func / {
        gsub(/{.*/, "{...}")
        print
        next
    }
    /^var |^const / { print; next }
    /^\/\// { print; next }
    ' "$1"
}

extract_rust() {
    awk '
    /^pub |^fn |^struct |^enum |^trait |^impl |^type |^const |^static |^mod / {
        print
        if (/{$/) { depth=1; while(depth>0 && (getline)>0) { if(/{/) depth++; if(/}/) depth-- } }
        next
    }
    /^use / { print; next }
    /^\/\/[\/!]/ { print; next }
    /^#\[/ { print; next }
    ' "$1"
}

extract_java() {
    awk '
    /^package |^import / { print; next }
    /^public |^private |^protected |^class |^interface |^enum |^@/ {
        print
        if (/{$/ && !/;$/) { depth=1; while(depth>0 && (getline)>0) { if(/{/) depth++; if(/}/) depth-- } }
        next
    }
    /^    (public|private|protected|static|final|abstract).*\(/ {
        gsub(/{.*/, "{...}")
        print
        next
    }
    /^\/\*\*/ { in_doc=1 }
    in_doc { print; if (/\*\//) in_doc=0; next }
    ' "$1"
}

extract_c() {
    awk '
    /^#include |^#define |^#ifndef |^#ifdef |^#endif/ { print; next }
    /^typedef / { print; next }
    /^struct |^enum |^union / {
        print
        if (/{/) { depth=1; while(depth>0 && (getline)>0) { print; if(/{/) depth++; if(/}/) depth-- } }
        next
    }
    /^[a-zA-Z_].*\(.*\)[ ]*[{;]?$/ && !/^  / {
        gsub(/{.*/, ";")
        print
        next
    }
    /^\/\// { print; next }
    /^\/\*/ { in_comment=1 }
    in_comment { print; if (/\*\//) in_comment=0; next }
    ' "$1"
}

for file in "${FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "File not found: $file" >&2
        continue
    fi

    FILE_LANG="${LANG:-$(detect_language "$file")}"
    TOTAL_LINES=$(wc -l < "$file")

    echo "=== $file ($FILE_LANG) ==="

    case "$FILE_LANG" in
        python) extract_python "$file" ;;
        typescript|javascript) extract_typescript "$file" ;;
        go) extract_go "$file" ;;
        rust) extract_rust "$file" ;;
        java) extract_java "$file" ;;
        c|cpp) extract_c "$file" ;;
        *)
            echo "Unknown language, showing grep for signatures:"
            grep -nE "^(export |function |class |def |fn |func |pub |interface |type |struct |enum )" "$file" | head -50
            ;;
    esac

    EXTRACTED=$(case "$FILE_LANG" in
        python) extract_python "$file" | wc -l ;;
        typescript|javascript) extract_typescript "$file" | wc -l ;;
        go) extract_go "$file" | wc -l ;;
        rust) extract_rust "$file" | wc -l ;;
        java) extract_java "$file" | wc -l ;;
        c|cpp) extract_c "$file" | wc -l ;;
        *) echo "?" ;;
    esac)

    echo ""
    echo "[Extracted $EXTRACTED lines from $TOTAL_LINES total]"
    echo ""
done
