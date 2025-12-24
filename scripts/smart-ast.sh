#!/usr/bin/env bash
# smart-ast.sh - Structural code search using ast-grep
# Usage: smart-ast.sh <pattern|shortcut> <path> [language] [options]
#
# Features:
# - Auto-detects language from file extensions
# - Common pattern shortcuts
# - Compact output mode

set -e

pattern="$1"
path="${2:-.}"
lang="${3:-}"
option="${4:-}"

# Find ast-grep
AST_GREP=""
if command -v ast-grep &>/dev/null; then
    AST_GREP="ast-grep"
elif [[ -x "$HOME/.cargo/bin/ast-grep" ]]; then
    AST_GREP="$HOME/.cargo/bin/ast-grep"
fi

if [[ -z "$AST_GREP" ]]; then
    echo "Error: ast-grep not found. Install with: cargo install ast-grep --locked"
    exit 1
fi

show_help() {
    cat << 'EOF'
Usage: smart-ast.sh <pattern|shortcut> <path> [language] [options]

Pattern Shortcuts:
  functions     Find all function definitions
  classes       Find all class definitions
  imports       Find all import statements
  calls:NAME    Find all calls to NAME (e.g., calls:print)
  async         Find all async functions
  decorators    Find all decorated functions
  todos         Find TODO/FIXME comments

Languages (auto-detected if not specified):
  python, javascript, typescript, rust, go, c, cpp, java, ruby

Options:
  compact       Show only file:line (no code)
  count         Just count matches
  json          JSON output

Examples:
  smart-ast.sh functions ./src python
  smart-ast.sh 'def $NAME($$$): $$$' ./src python
  smart-ast.sh calls:print ./src python compact
  smart-ast.sh imports ./src typescript
  smart-ast.sh 'console.log($$$)' ./src javascript

EOF
    exit 0
}

[[ -z "$pattern" || "$pattern" == "-h" || "$pattern" == "--help" ]] && show_help

# Auto-detect language from path
detect_language() {
    local p="$1"
    if [[ -d "$p" ]]; then
        # Check most common file in directory
        if ls "$p"/*.py 2>/dev/null | head -1 | grep -q .; then echo "python"
        elif ls "$p"/*.ts 2>/dev/null | head -1 | grep -q .; then echo "typescript"
        elif ls "$p"/*.js 2>/dev/null | head -1 | grep -q .; then echo "javascript"
        elif ls "$p"/*.rs 2>/dev/null | head -1 | grep -q .; then echo "rust"
        elif ls "$p"/*.go 2>/dev/null | head -1 | grep -q .; then echo "go"
        elif ls "$p"/*.cpp 2>/dev/null | head -1 | grep -q .; then echo "cpp"
        elif ls "$p"/*.java 2>/dev/null | head -1 | grep -q .; then echo "java"
        elif ls "$p"/*.rb 2>/dev/null | head -1 | grep -q .; then echo "ruby"
        fi
    else
        case "$p" in
            *.py) echo "python" ;;
            *.ts|*.tsx) echo "typescript" ;;
            *.js|*.jsx|*.mjs) echo "javascript" ;;
            *.rs) echo "rust" ;;
            *.go) echo "go" ;;
            *.c|*.h) echo "c" ;;
            *.cpp|*.cc|*.hpp) echo "cpp" ;;
            *.java) echo "java" ;;
            *.rb) echo "ruby" ;;
        esac
    fi
}

# Use provided language or auto-detect
if [[ -z "$lang" ]]; then
    lang=$(detect_language "$path")
fi

if [[ -z "$lang" ]]; then
    echo "Error: Could not detect language. Please specify: smart-ast.sh <pattern> <path> <language>"
    exit 1
fi

# Expand pattern shortcuts
expand_pattern() {
    local p="$1"
    local l="$2"

    case "$p" in
        functions)
            case "$l" in
                python) echo 'def $NAME($$$): $$$' ;;
                javascript|typescript) echo 'function $NAME($$$) { $$$ }' ;;
                rust) echo 'fn $NAME($$$) { $$$ }' ;;
                go) echo 'func $NAME($$$) { $$$ }' ;;
                java|cpp|c) echo '$RET $NAME($$$) { $$$ }' ;;
                ruby) echo 'def $NAME($$$) $$$ end' ;;
                *) echo "$p" ;;
            esac
            ;;
        classes)
            case "$l" in
                python) echo 'class $NAME: $$$' ;;
                javascript|typescript) echo 'class $NAME { $$$ }' ;;
                rust) echo 'struct $NAME { $$$ }' ;;
                java|cpp) echo 'class $NAME { $$$ }' ;;
                ruby) echo 'class $NAME $$$ end' ;;
                *) echo "$p" ;;
            esac
            ;;
        imports)
            case "$l" in
                python) echo 'import $$$' ;;
                javascript|typescript) echo 'import $$$' ;;
                rust) echo 'use $$$;' ;;
                go) echo 'import $$$' ;;
                java) echo 'import $$$;' ;;
                c|cpp) echo '#include $$$' ;;
                *) echo "$p" ;;
            esac
            ;;
        calls:*)
            local func_name="${p#calls:}"
            case "$l" in
                python|ruby) echo "${func_name}(\$\$\$)" ;;
                javascript|typescript|java|cpp|c|rust|go) echo "${func_name}(\$\$\$)" ;;
                *) echo "$p" ;;
            esac
            ;;
        async)
            case "$l" in
                python) echo 'async def $NAME($$$): $$$' ;;
                javascript|typescript) echo 'async function $NAME($$$) { $$$ }' ;;
                rust) echo 'async fn $NAME($$$) { $$$ }' ;;
                *) echo "$p" ;;
            esac
            ;;
        decorators)
            case "$l" in
                python) echo '@$DEC def $NAME($$$): $$$' ;;
                typescript) echo '@$DEC class $NAME { $$$ }' ;;
                *) echo "$p" ;;
            esac
            ;;
        *)
            echo "$p"
            ;;
    esac
}

actual_pattern=$(expand_pattern "$pattern" "$lang")

# Run ast-grep with options
case "$option" in
    compact)
        # Show only the first line of each match block
        $AST_GREP --pattern "$actual_pattern" --lang "$lang" "$path" 2>/dev/null | grep -E "^/" | awk -F: '
        {
            file=$1; line=$2
            if (file != last_file || line > last_line + 1) {
                print $0
            }
            last_file = file
            last_line = line
        }' | cut -d: -f1-3 | head -50
        ;;
    count)
        $AST_GREP --pattern "$actual_pattern" --lang "$lang" "$path" 2>/dev/null | grep -E "^/" | wc -l
        ;;
    json)
        $AST_GREP --pattern "$actual_pattern" --lang "$lang" "$path" --json 2>/dev/null
        ;;
    *)
        $AST_GREP --pattern "$actual_pattern" --lang "$lang" "$path" 2>/dev/null | head -100
        ;;
esac
