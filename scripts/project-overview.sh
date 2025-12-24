#!/usr/bin/env bash
# Quick project overview - structure, file counts, key files
# Usage: project-overview.sh [directory]

set -euo pipefail

dir="${1:-.}"

echo "=== Project Overview: $dir ==="
echo ""

# Check for common project indicators
echo "## Project Type:"
[[ -f "$dir/package.json" ]] && echo "  - Node.js (package.json)"
[[ -f "$dir/Cargo.toml" ]] && echo "  - Rust (Cargo.toml)"
[[ -f "$dir/go.mod" ]] && echo "  - Go (go.mod)"
[[ -f "$dir/CMakeLists.txt" ]] && echo "  - CMake (CMakeLists.txt)"
[[ -f "$dir/Makefile" ]] && echo "  - Make (Makefile)"
[[ -f "$dir/pyproject.toml" || -f "$dir/setup.py" ]] && echo "  - Python"
[[ -f "$dir/pom.xml" ]] && echo "  - Java/Maven (pom.xml)"
[[ -f "$dir/build.gradle" ]] && echo "  - Gradle (build.gradle)"
compgen -G "$dir/*.pro" >/dev/null 2>&1 && echo "  - Qt (*.pro)"
echo ""

# Directory structure (depth 2)
echo "## Directory Structure:"
if command -v tree &>/dev/null; then
    tree -L 2 -d --noreport "$dir" 2>/dev/null | head -30 || find "$dir" -maxdepth 2 -type d | head -30
else
    find "$dir" -maxdepth 2 -type d | grep -v "node_modules\|\.git\|build\|dist\|__pycache__" | head -30
fi
echo ""

# File counts by extension
echo "## File Counts by Type:"
find "$dir" -type f -name "*.*" \
    ! -path "*/.git/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/build/*" \
    ! -path "*/dist/*" \
    ! -path "*/__pycache__/*" \
    2>/dev/null | \
    sed 's/.*\.//' | sort | uniq -c | sort -rn | head -15

echo ""

# Largest source files
echo "## Largest Source Files:"
find "$dir" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.cpp" -o -name "*.cc" -o -name "*.c" -o -name "*.h" -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.qml" \) \
    ! -path "*/.git/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/build/*" \
    -exec wc -l {} \; 2>/dev/null | sort -rn | head -10

echo ""

# Recently modified
echo "## Recently Modified (last 24h):"
find "$dir" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.cpp" -o -name "*.cc" -o -name "*.h" -o -name "*.go" -o -name "*.rs" \) \
    ! -path "*/.git/*" \
    ! -path "*/node_modules/*" \
    -mtime -1 2>/dev/null | head -10 || echo "  (none)"

echo ""

# Key files
echo "## Key Files:"
for f in README.md CLAUDE.md .claude/settings.json package.json Cargo.toml CMakeLists.txt Makefile pyproject.toml; do
    [[ -f "$dir/$f" ]] && echo "  - $f"
done
