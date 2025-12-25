#!/usr/bin/env bash
# impact-analysis.sh - Show what files depend on or are affected by a given file
# Usage: impact-analysis.sh <file> [search_path]
#
# Features:
# - Finds files that import/include the target
# - Finds what the target imports/includes
# - Identifies related test files
# - Works across Python, JS/TS, C/C++, Go, Rust

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

file="$1"
search_path="${2:-.}"

if [[ -z "$file" ]]; then
    echo "Usage: impact-analysis.sh <file> [search_path]"
    echo ""
    echo "Examples:"
    echo "  impact-analysis.sh src/auth.py"
    echo "  impact-analysis.sh src/utils/helpers.ts ./src"
    exit 1
fi

if [[ ! -f "$file" ]]; then
    echo "Error: File not found: $file"
    exit 1
fi

# Get file info
filename=$(basename "$file")
name_no_ext="${filename%.*}"
extension="${filename##*.}"
lang=$(detect_language "$file")
dir=$(dirname "$file")

# Determine import patterns based on language
case "$lang" in
    python)
        # Python imports
        import_pattern="^(from|import)\s+.*$name_no_ext|^from\s+\.\s+import.*$name_no_ext"
        self_import_pattern="^(from|import)\s+"
        file_glob="*.py"
        ;;
    typescript|javascript)
        # JavaScript/TypeScript imports
        import_pattern="(require|import).*['\"].*$name_no_ext['\"]|from\s+['\"].*$name_no_ext['\"]"
        self_import_pattern="^import\s+|require\s*\("
        file_glob="*.{js,jsx,ts,tsx,mjs}"
        ;;
    c|cpp)
        # C/C++ includes
        import_pattern="#include.*$filename|#include.*$name_no_ext\.(h|hpp)"
        self_import_pattern="^#include"
        file_glob="*.{c,h,cpp,cc,cxx,hpp,hxx}"
        ;;
    go)
        # Go imports
        import_pattern="import.*$name_no_ext|\".*/$name_no_ext\""
        self_import_pattern="^import"
        file_glob="*.go"
        ;;
    rust)
        # Rust imports
        import_pattern="use.*$name_no_ext|mod\s+$name_no_ext"
        self_import_pattern="^use\s+|^mod\s+"
        file_glob="*.rs"
        ;;
    *)
        # Generic - try common patterns
        import_pattern="$name_no_ext"
        self_import_pattern="import|include|require"
        file_glob="*"
        ;;
esac

echo "=== Impact Analysis: $file ==="
echo ""

# Find what this file imports
echo "## Imports (what $filename uses):"
if grep -E "$self_import_pattern" "$file" 2>/dev/null | head -15; then
    :
else
    echo "  (no imports found)"
fi
echo ""

# Find dependents using fd if available, otherwise find
echo "## Dependents (files that use $filename):"
FD=$(find_fd)

dependents_found=0
# Use ripgrep if available (fastest), then grep -r
if command -v rg &>/dev/null; then
    results=$(rg -l "$import_pattern" "$search_path" --glob "*.${extension}" 2>/dev/null | grep -v "^$file$" | head -20)
    if [[ -n "$results" ]]; then
        echo "$results"
        dependents_found=1
    fi
elif [[ -n "$FD" ]]; then
    # Use fd + grep (slower but still efficient)
    results=$($FD -e "${extension}" . "$search_path" 2>/dev/null | xargs -r grep -lE "$import_pattern" 2>/dev/null | grep -v "^$file$" | head -20)
    if [[ -n "$results" ]]; then
        echo "$results"
        dependents_found=1
    fi
else
    # Fallback to grep -r
    results=$(grep -rlE "$import_pattern" "$search_path" --include="$file_glob" 2>/dev/null | grep -v "^$file$" | head -20)
    if [[ -n "$results" ]]; then
        echo "$results"
        dependents_found=1
    fi
fi

if [[ $dependents_found -eq 0 ]]; then
    echo "  (no dependents found)"
fi
echo ""

# Find related test files
echo "## Related Tests:"
test_patterns=(
    "test_${name_no_ext}"
    "${name_no_ext}_test"
    "${name_no_ext}.test"
    "${name_no_ext}.spec"
    "tests/*${name_no_ext}*"
    "test/*${name_no_ext}*"
    "__tests__/*${name_no_ext}*"
)

tests_found=0
for pattern in "${test_patterns[@]}"; do
    if [[ -n "$FD" ]]; then
        matches=$($FD "$pattern" "$search_path" 2>/dev/null | head -5)
    else
        matches=$(find "$search_path" -name "*$pattern*" -type f 2>/dev/null | head -5)
    fi
    if [[ -n "$matches" ]]; then
        echo "$matches"
        tests_found=1
    fi
done

if [[ $tests_found -eq 0 ]]; then
    echo "  (no test files found)"
fi
echo ""

# Summary
echo "## Summary:"
dep_count=$(grep -rlE "$import_pattern" "$search_path" --include="*.${extension}" 2>/dev/null | grep -v "^$file$" | wc -l)
echo "  - Dependents: ~$dep_count files may be affected by changes"
echo "  - Check these files when refactoring $filename"
