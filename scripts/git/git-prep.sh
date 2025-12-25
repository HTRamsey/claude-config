#!/usr/bin/env bash
# git-prep.sh - Pre-commit preparation and validation
#
# Usage:
#   git-prep.sh              Run all checks
#   git-prep.sh --fix        Run checks and auto-fix where possible
#   git-prep.sh --staged     Only check staged files
#   git-prep.sh --quick      Quick checks only (no tests)
#
# Checks:
#   1. No merge conflicts
#   2. No debug statements
#   3. No secrets/credentials
#   4. Linting passes
#   5. Tests pass (unless --quick)
#   6. Commit message template

SCRIPT_VERSION="1.0.0"

set -euo pipefail

# Load common utilities
source "$(dirname "$0")/../lib/common.sh"

FIX_MODE=false
STAGED_ONLY=false
QUICK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            cat << 'EOF'
git-prep.sh - Pre-commit preparation and validation

Usage:
  git-prep.sh [options]

Options:
  --fix        Auto-fix issues where possible (formatting, imports)
  --staged     Only check staged files
  --quick      Skip tests, just run linting/formatting checks
  --verbose    Show detailed output

Checks performed:
  1. Merge conflicts  - Check for unresolved conflict markers
  2. Debug statements - console.log, print(), debugger, etc.
  3. Secrets          - API keys, passwords, tokens
  4. Formatting       - Run prettier/black/gofmt
  5. Linting          - Run eslint/pylint/clippy
  6. Tests            - Run test suite (skip with --quick)

Examples:
  # Full check before commit
  git-prep.sh

  # Quick format check with auto-fix
  git-prep.sh --fix --quick

  # Check only staged files
  git-prep.sh --staged

EOF
            exit 0
            ;;
        --fix)
            FIX_MODE=true
            shift
            ;;
        --staged)
            STAGED_ONLY=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Track issues
ISSUES=()
WARNINGS=()

log_pass() { echo -e "${GREEN}✓${NC} $1"; }
log_fail() { echo -e "${RED}✗${NC} $1"; ISSUES+=("$1"); }
log_warn() { echo -e "${YELLOW}!${NC} $1"; WARNINGS+=("$1"); }
log_info() { echo -e "  $1"; }

# Get files to check
get_files() {
    local ext="$1"
    if $STAGED_ONLY; then
        git diff --cached --name-only --diff-filter=ACMR | grep -E "\.$ext$" || true
    else
        git ls-files | grep -E "\.$ext$" || true
    fi
}

echo "=== Git Pre-Commit Checks ==="
echo ""

# 1. Check for merge conflicts
echo "## Checking for merge conflicts..."
conflicts=$(git diff --check 2>/dev/null | grep -c "conflict" || echo 0)
if [[ "$conflicts" -gt 0 ]]; then
    log_fail "Found $conflicts unresolved merge conflicts"
    git diff --check 2>/dev/null | head -10
else
    log_pass "No merge conflicts"
fi

# 2. Check for debug statements
echo ""
echo "## Checking for debug statements..."
debug_patterns='console\.log\(|debugger|print\(.*DEBUG|pdb\.set_trace|breakpoint\(\)|binding\.pry'

if $STAGED_ONLY; then
    debug_files=$(git diff --cached --name-only -z | xargs -0 grep -l -E "$debug_patterns" 2>/dev/null || true)
else
    debug_files=$(git ls-files -z | xargs -0 grep -l -E "$debug_patterns" 2>/dev/null | head -10 || true)
fi

if [[ -n "$debug_files" ]]; then
    log_warn "Found debug statements in:"
    echo "$debug_files" | head -5 | while read f; do log_info "$f"; done
else
    log_pass "No debug statements found"
fi

# 3. Check for secrets/credentials
echo ""
echo "## Checking for potential secrets..."
secret_patterns='(password|secret|api.?key|token|credential)\s*[:=]\s*["\x27][^"\x27]{8,}|BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY'

if $STAGED_ONLY; then
    secret_files=$(git diff --cached --name-only -z | xargs -0 grep -l -iE "$secret_patterns" 2>/dev/null | grep -v "\.md$\|\.lock$\|\.sum$" || true)
else
    secret_files=$(git ls-files -z | xargs -0 grep -l -iE "$secret_patterns" 2>/dev/null | grep -v "\.md$\|\.lock$\|\.sum$" | head -10 || true)
fi

if [[ -n "$secret_files" ]]; then
    log_fail "Possible secrets detected in:"
    echo "$secret_files" | while read f; do log_info "$f"; done
else
    log_pass "No obvious secrets detected"
fi

# 4. Linting/Formatting checks
echo ""
echo "## Running linters..."

# JavaScript/TypeScript
if [[ -f "package.json" ]]; then
    if $FIX_MODE && has_command npx; then
        if [[ -f ".prettierrc" || -f "prettier.config.js" ]]; then
            log_info "Running prettier --write..."
            npx prettier --write "**/*.{js,ts,tsx,json}" 2>/dev/null || true
        fi
    fi

    if has_command npx && [[ -f ".eslintrc.js" || -f ".eslintrc.json" || -f "eslint.config.js" ]]; then
        if npx eslint . --max-warnings=0 2>/dev/null; then
            log_pass "ESLint passed"
        else
            log_fail "ESLint found issues"
        fi
    fi
fi

# Python
if [[ -f "pyproject.toml" || -f "setup.py" ]]; then
    py_files=$(get_files "py")
    if [[ -n "$py_files" ]]; then
        if $FIX_MODE && has_command black; then
            log_info "Running black..."
            echo "$py_files" | xargs black 2>/dev/null || true
        fi

        if has_command ruff; then
            if $FIX_MODE; then
                echo "$py_files" | xargs ruff check --fix 2>/dev/null || true
            fi
            if echo "$py_files" | xargs ruff check 2>/dev/null; then
                log_pass "Ruff passed"
            else
                log_fail "Ruff found issues"
            fi
        elif has_command pylint; then
            if echo "$py_files" | head -5 | xargs pylint --errors-only 2>/dev/null; then
                log_pass "Pylint passed (errors only)"
            else
                log_fail "Pylint found errors"
            fi
        fi
    fi
fi

# Rust
if [[ -f "Cargo.toml" ]]; then
    if $FIX_MODE && has_command cargo; then
        log_info "Running cargo fmt..."
        cargo fmt 2>/dev/null || true
    fi

    if has_command cargo; then
        if cargo clippy --all-targets --all-features -- -D warnings 2>/dev/null; then
            log_pass "Clippy passed"
        else
            log_warn "Clippy found warnings"
        fi
    fi
fi

# Go
if [[ -f "go.mod" ]]; then
    if $FIX_MODE && has_command gofmt; then
        log_info "Running gofmt..."
        gofmt -w . 2>/dev/null || true
    fi

    if has_command go; then
        if go vet ./... 2>/dev/null; then
            log_pass "go vet passed"
        else
            log_fail "go vet found issues"
        fi
    fi
fi

# 5. Run tests (unless quick mode)
if ! $QUICK; then
    echo ""
    echo "## Running tests..."

    if [[ -f "package.json" ]] && grep -q '"test"' package.json; then
        if npm test 2>/dev/null; then
            log_pass "npm test passed"
        else
            log_fail "npm test failed"
        fi
    elif [[ -f "Cargo.toml" ]]; then
        if cargo test 2>/dev/null; then
            log_pass "cargo test passed"
        else
            log_fail "cargo test failed"
        fi
    elif [[ -f "pyproject.toml" ]] || [[ -d "tests" ]]; then
        if has_command pytest; then
            if pytest --tb=short 2>/dev/null; then
                log_pass "pytest passed"
            else
                log_fail "pytest failed"
            fi
        fi
    elif [[ -f "go.mod" ]]; then
        if go test ./... 2>/dev/null; then
            log_pass "go test passed"
        else
            log_fail "go test failed"
        fi
    else
        log_info "No test command detected"
    fi
fi

# Summary
echo ""
echo "=== Summary ==="

if [[ ${#ISSUES[@]} -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
    [[ ${#WARNINGS[@]} -gt 0 ]] && echo -e "${YELLOW}Warnings: ${#WARNINGS[@]}${NC}"
    echo ""
    echo "Ready to commit. Suggested message format:"
    echo "  type(scope): description"
    echo ""
    echo "Types: feat, fix, docs, style, refactor, test, chore"
    exit 0
else
    echo -e "${RED}Issues found: ${#ISSUES[@]}${NC}"
    for issue in "${ISSUES[@]}"; do
        echo "  - $issue"
    done
    [[ ${#WARNINGS[@]} -gt 0 ]] && echo -e "${YELLOW}Warnings: ${#WARNINGS[@]}${NC}"
    echo ""
    echo "Fix issues before committing."
    exit 1
fi
