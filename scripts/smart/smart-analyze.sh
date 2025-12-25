#!/usr/bin/env bash
# smart-analyze.sh - Unified code analysis tool
#
# Usage:
#   smart-analyze.sh file <path>      Show file dependencies (imports, importers)
#   smart-analyze.sh impact <path>    Impact analysis for changes
#   smart-analyze.sh project [path]   Project overview and stats
#   smart-analyze.sh deps <path>      Dependency graph (what imports what)
#
# Combines: find-related.sh, impact-analysis.sh, project-overview.sh

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

show_help() {
    cat << 'EOF'
smart-analyze.sh - Unified code analysis tool

Usage:
  smart-analyze.sh <command> [args]

Commands:
  file <path>       What a file imports and what imports it
  impact <path>     Impact analysis - what's affected by changes
  project [path]    Project overview, structure, and stats
  deps <path>       Show dependency relationships

Examples:
  smart-analyze.sh file src/auth.py
  smart-analyze.sh impact src/utils.ts
  smart-analyze.sh project ./myapp
  smart-analyze.sh deps src/

EOF
    exit 0
}

# Common excludes for find operations
EXCLUDES=(-not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/build/*" -not -path "*/dist/*" -not -path "*/__pycache__/*" -not -path "*/target/*" -not -path "*/.venv/*")

# ============================================================================
# FILE COMMAND - What a file imports and what imports it
# ============================================================================
cmd_file() {
    local file="$1"

    if [[ -z "$file" || ! -f "$file" ]]; then
        echo "Usage: smart-analyze.sh file <path>"
        exit 1
    fi

    local filename=$(basename "$file")
    local name_no_ext="${filename%.*}"
    local lang=$(detect_language "$file")
    local search_dir=$(dirname "$file")

    # Go up to find project root if we're deep
    while [[ "$search_dir" != "/" && ! -f "$search_dir/package.json" && ! -f "$search_dir/Cargo.toml" && ! -f "$search_dir/go.mod" && ! -f "$search_dir/pyproject.toml" && ! -d "$search_dir/.git" ]]; do
        search_dir=$(dirname "$search_dir")
    done
    [[ "$search_dir" == "/" ]] && search_dir=$(dirname "$file")

    echo "=== File Analysis: $file ==="
    echo "Language: $lang | Search root: $search_dir"
    echo ""

    # What this file imports
    echo "## Imports (what $filename uses):"
    case "$lang" in
        python)
            grep -h "^import \|^from .* import" "$file" 2>/dev/null | sed 's/import //;s/from //;s/ import.*//' | sort -u || echo "  (none)"
            ;;
        typescript|javascript)
            grep -h "^import .* from \|require(" "$file" 2>/dev/null | sed "s/.*from ['\"]//;s/['\"].*//;s/.*require(['\"]//;s/['\"]).*//;" | sort -u || echo "  (none)"
            ;;
        c|cpp)
            grep -h "^#include" "$file" 2>/dev/null | sed 's/#include [<"]//;s/[>"]$//' | sort -u || echo "  (none)"
            ;;
        go)
            sed -n '/^import/,/)/p' "$file" 2>/dev/null | grep -v "import\|)\|^$" | tr -d '\t"' | sort -u || echo "  (none)"
            ;;
        rust)
            grep -h "^use " "$file" 2>/dev/null | sed 's/use //;s/;$//' | sort -u || echo "  (none)"
            ;;
        *)
            echo "  (import detection not supported for $lang)"
            ;;
    esac

    echo ""
    echo "## Importers (files that use $filename):"

    # Find files that reference this file
    local results=""
    if has_command rg; then
        results=$(rg -l "import.*$name_no_ext|from.*$name_no_ext|require.*$name_no_ext|#include.*$filename" "$search_dir" \
            --type-add 'code:*.{py,ts,tsx,js,jsx,cpp,cc,c,h,hpp,go,rs,java,kt,rb}' \
            -t code 2>/dev/null | grep -v "^$file$" | head -20) || true
    else
        results=$(grep -rl "import.*$name_no_ext\|from.*$name_no_ext\|require.*$name_no_ext\|#include.*$filename" "$search_dir" \
            --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.cpp" --include="*.go" \
            2>/dev/null | grep -v "^$file$" | head -20) || true
    fi

    if [[ -n "$results" ]]; then
        echo "$results"
    else
        echo "  (no files import this)"
    fi

    echo ""
    echo "## Related Files:"
    FD=$(find_fd)
    if [[ -n "$FD" ]]; then
        $FD "$name_no_ext" "$search_dir" --type f 2>/dev/null | grep -v "^$file$" | head -10 || echo "  (none)"
    else
        find "$search_dir" -name "*$name_no_ext*" -type f "${EXCLUDES[@]}" 2>/dev/null | grep -v "^$file$" | head -10 || echo "  (none)"
    fi
}

# ============================================================================
# IMPACT COMMAND - What's affected by changes to a file
# ============================================================================
cmd_impact() {
    local file="$1"
    local search_path="${2:-.}"

    if [[ -z "$file" ]]; then
        echo "Usage: smart-analyze.sh impact <file> [search_path]"
        exit 1
    fi

    if [[ ! -f "$file" ]]; then
        echo "Error: File not found: $file"
        exit 1
    fi

    local filename=$(basename "$file")
    local name_no_ext="${filename%.*}"
    local extension="${filename##*.}"
    local lang=$(detect_language "$file")

    # Determine import patterns
    local import_pattern file_glob
    case "$lang" in
        python)
            import_pattern="^(from|import)\s+.*$name_no_ext|^from\s+\.\s+import.*$name_no_ext"
            file_glob="*.py"
            ;;
        typescript|javascript)
            import_pattern="(require|import).*['\"].*$name_no_ext['\"]|from\s+['\"].*$name_no_ext['\"]"
            file_glob="*.{js,jsx,ts,tsx,mjs}"
            ;;
        c|cpp)
            import_pattern="#include.*$filename|#include.*$name_no_ext\.(h|hpp)"
            file_glob="*.{c,h,cpp,cc,cxx,hpp,hxx}"
            ;;
        go)
            import_pattern="import.*$name_no_ext|\".*/$name_no_ext\""
            file_glob="*.go"
            ;;
        rust)
            import_pattern="use.*$name_no_ext|mod\s+$name_no_ext"
            file_glob="*.rs"
            ;;
        *)
            import_pattern="$name_no_ext"
            file_glob="*"
            ;;
    esac

    echo "=== Impact Analysis: $file ==="
    echo "Language: $lang"
    echo ""

    # Direct dependents
    echo "## Direct Dependents (files that import $filename):"
    local dep_count=0
    if has_command rg; then
        local results=$(rg -l "$import_pattern" "$search_path" --glob "*.${extension}" 2>/dev/null | grep -v "^$file$" | head -20) || true
        if [[ -n "$results" ]]; then
            echo "$results"
            dep_count=$(echo "$results" | wc -l)
        else
            echo "  (none found)"
        fi
    else
        local results=$(grep -rlE "$import_pattern" "$search_path" --include="$file_glob" 2>/dev/null | grep -v "^$file$" | head -20) || true
        if [[ -n "$results" ]]; then
            echo "$results"
            dep_count=$(echo "$results" | wc -l)
        else
            echo "  (none found)"
        fi
    fi

    echo ""
    echo "## Related Tests:"
    local test_patterns=("test_${name_no_ext}" "${name_no_ext}_test" "${name_no_ext}.test" "${name_no_ext}.spec")
    local tests_found=0
    FD=$(find_fd)

    for pattern in "${test_patterns[@]}"; do
        local matches=""
        if [[ -n "$FD" ]]; then
            matches=$($FD "$pattern" "$search_path" 2>/dev/null | head -5) || true
        else
            matches=$(find "$search_path" -name "*$pattern*" -type f "${EXCLUDES[@]}" 2>/dev/null | head -5) || true
        fi
        if [[ -n "$matches" ]]; then
            echo "$matches"
            tests_found=1
        fi
    done
    [[ $tests_found -eq 0 ]] && echo "  (no test files found)"

    echo ""
    echo "## Summary:"
    echo "  - Direct dependents: $dep_count files"
    echo "  - Changes to $filename may affect these files"
    echo "  - Consider running related tests before committing"
}

# ============================================================================
# PROJECT COMMAND - Project overview and stats
# ============================================================================
cmd_project() {
    local dir="${1:-.}"

    echo "=== Project Overview: $dir ==="
    echo ""

    # Project type detection
    echo "## Project Type:"
    local found=0
    [[ -f "$dir/package.json" ]] && { echo "  - Node.js (package.json)"; found=1; }
    [[ -f "$dir/Cargo.toml" ]] && { echo "  - Rust (Cargo.toml)"; found=1; }
    [[ -f "$dir/go.mod" ]] && { echo "  - Go (go.mod)"; found=1; }
    [[ -f "$dir/CMakeLists.txt" ]] && { echo "  - CMake (CMakeLists.txt)"; found=1; }
    [[ -f "$dir/Makefile" ]] && { echo "  - Make (Makefile)"; found=1; }
    [[ -f "$dir/pyproject.toml" || -f "$dir/setup.py" || -f "$dir/requirements.txt" ]] && { echo "  - Python"; found=1; }
    [[ -f "$dir/pom.xml" ]] && { echo "  - Java/Maven (pom.xml)"; found=1; }
    [[ -f "$dir/build.gradle" || -f "$dir/build.gradle.kts" ]] && { echo "  - Gradle"; found=1; }
    compgen -G "$dir/*.pro" >/dev/null 2>&1 && { echo "  - Qt (*.pro)"; found=1; }
    [[ $found -eq 0 ]] && echo "  - Unknown"
    echo ""

    # Directory structure
    echo "## Structure (depth 2):"
    EZA=$(find_eza)
    if [[ -n "$EZA" ]]; then
        $EZA --tree --level=2 --only-dirs --git-ignore "$dir" 2>/dev/null | head -25 || find "$dir" -maxdepth 2 -type d "${EXCLUDES[@]}" 2>/dev/null | head -25
    elif has_command tree; then
        tree -L 2 -d --noreport "$dir" 2>/dev/null | head -25
    else
        find "$dir" -maxdepth 2 -type d "${EXCLUDES[@]}" 2>/dev/null | head -25
    fi
    echo ""

    # File counts
    echo "## File Counts by Type:"
    find "$dir" -type f -name "*.*" "${EXCLUDES[@]}" 2>/dev/null | \
        sed 's/.*\.//' | sort | uniq -c | sort -rn | head -12
    echo ""

    # Code stats with tokei if available
    if has_command tokei; then
        echo "## Code Statistics (tokei):"
        tokei "$dir" --exclude node_modules --exclude .git --exclude build --exclude dist --compact 2>/dev/null | head -20
        echo ""
    fi

    # Largest files
    echo "## Largest Source Files:"
    find "$dir" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.cpp" -o -name "*.c" -o -name "*.h" -o -name "*.go" -o -name "*.rs" -o -name "*.java" \) \
        "${EXCLUDES[@]}" -exec wc -l {} \; 2>/dev/null | sort -rn | head -8
    echo ""

    # Recently modified
    echo "## Recently Modified (24h):"
    find "$dir" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.cpp" -o -name "*.go" -o -name "*.rs" \) \
        "${EXCLUDES[@]}" -mtime -1 2>/dev/null | head -8 || echo "  (none)"
    echo ""

    # Key files
    echo "## Key Files:"
    for f in README.md CLAUDE.md .claude/settings.json package.json Cargo.toml CMakeLists.txt Makefile pyproject.toml go.mod; do
        [[ -f "$dir/$f" ]] && echo "  - $f"
    done
}

# ============================================================================
# DEPS COMMAND - Dependency relationships
# ============================================================================
cmd_deps() {
    local path="${1:-.}"

    echo "=== Dependency Analysis: $path ==="
    echo ""

    if [[ -f "$path" ]]; then
        # Single file - show its dependencies
        cmd_file "$path"
    else
        # Directory - show top-level import relationships
        local lang=$(detect_language "$path")
        echo "## Most-imported files (high impact):"

        case "$lang" in
            python)
                rg "^from \.|^import " "$path" --type py -o 2>/dev/null | \
                    sed 's/from //;s/import //;s/ .*//' | \
                    sort | uniq -c | sort -rn | head -15 || echo "  (no imports found)"
                ;;
            typescript|javascript)
                rg "from ['\"]\./" "$path" --type ts --type js -o 2>/dev/null | \
                    sed "s/from ['\"]//;s/['\"]$//" | \
                    sort | uniq -c | sort -rn | head -15 || echo "  (no imports found)"
                ;;
            *)
                echo "  (dependency analysis not implemented for $lang)"
                ;;
        esac

        echo ""
        echo "## Orphan files (not imported by anything):"
        # This is expensive, so limit scope
        local count=0
        for f in $(find "$path" -maxdepth 2 -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" \) "${EXCLUDES[@]}" 2>/dev/null | head -20); do
            local name=$(basename "${f%.*}")
            if ! rg -q "import.*$name|from.*$name|require.*$name" "$path" 2>/dev/null; then
                echo "  $f"
                ((count++))
                [[ $count -ge 10 ]] && break
            fi
        done
        [[ $count -eq 0 ]] && echo "  (none found in top 20 files)"
    fi
}

# ============================================================================
# MAIN
# ============================================================================
case "${1:-}" in
    -h|--help|"") show_help ;;
    file) shift; cmd_file "$@" ;;
    impact) shift; cmd_impact "$@" ;;
    project) shift; cmd_project "$@" ;;
    deps) shift; cmd_deps "$@" ;;
    *)
        echo "Unknown command: $1"
        echo "Try: smart-analyze.sh --help"
        exit 1
        ;;
esac
