#!/usr/bin/env bash
# smoke-test.sh - Basic smoke tests for critical scripts
#
# Usage: ./smoke-test.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
SKIPPED=0

log_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASSED++)); }
log_fail() { echo -e "${RED}✗${NC} $1"; ((FAILED++)); }
log_skip() { echo -e "${YELLOW}○${NC} $1"; ((SKIPPED++)); }

echo "=== Script Smoke Tests ==="
echo ""

# ============================================================
# compress.sh tests
# ============================================================
echo "## compress.sh"

if "$SCRIPT_DIR/compress.sh" --help >/dev/null 2>&1; then
    log_pass "compress.sh --help"
else
    log_fail "compress.sh --help"
fi

if "$SCRIPT_DIR/compress.sh" --version 2>&1 | grep -q "version"; then
    log_pass "compress.sh --version"
else
    log_fail "compress.sh --version"
fi

if echo "error: test" | "$SCRIPT_DIR/compress.sh" -t build --json 2>&1 | grep -q '"type":"build"'; then
    log_pass "compress.sh -t build --json"
else
    log_fail "compress.sh -t build --json"
fi

compress_output=$("$SCRIPT_DIR/compress.sh" 2>&1 || true)
if echo "$compress_output" | grep -qi "error"; then
    log_pass "compress.sh missing --type fails correctly"
else
    log_fail "compress.sh missing --type should fail"
fi

echo ""

# ============================================================
# common.sh tests
# ============================================================
echo "## common.sh"

if source "$SCRIPT_DIR/common.sh" 2>/dev/null; then
    log_pass "common.sh sources without error"
else
    log_fail "common.sh sources without error"
fi

if type log_error &>/dev/null; then
    log_pass "common.sh provides log_error"
else
    log_fail "common.sh provides log_error"
fi

if has_command bash; then
    log_pass "common.sh has_command works"
else
    log_fail "common.sh has_command works"
fi

echo ""

# ============================================================
# parallel.sh tests
# ============================================================
echo "## parallel.sh"

if "$SCRIPT_DIR/parallel.sh" --help >/dev/null 2>&1; then
    log_pass "parallel.sh --help"
else
    log_fail "parallel.sh --help"
fi

# parallel.sh uses wait -n which may hang on some bash versions
# Skip for now - the --help test verifies basic functionality
log_skip "parallel.sh execution (wait -n requires bash 4.3+)"

echo ""

# ============================================================
# git-prep.sh tests
# ============================================================
echo "## git-prep.sh"

if "$SCRIPT_DIR/git-prep.sh" --help >/dev/null 2>&1; then
    log_pass "git-prep.sh --help"
else
    log_fail "git-prep.sh --help"
fi

echo ""

# ============================================================
# offload-grep.sh tests
# ============================================================
echo "## offload-grep.sh"

if "$SCRIPT_DIR/offload-grep.sh" 'echo' "$SCRIPT_DIR" 5 >/dev/null 2>&1; then
    log_pass "offload-grep.sh basic search"
else
    log_fail "offload-grep.sh basic search"
fi

echo ""

# ============================================================
# smart-preview.sh tests
# ============================================================
echo "## smart-preview.sh"

if "$SCRIPT_DIR/smart-preview.sh" "$SCRIPT_DIR/common.sh" >/dev/null 2>&1; then
    log_pass "smart-preview.sh on self"
else
    log_fail "smart-preview.sh on self"
fi

echo ""

# ============================================================
# health-check.sh - skipped (calls claude CLI)
# ============================================================
echo "## health-check.sh"
log_skip "health-check.sh (calls claude CLI)"

echo ""

# ============================================================
# Summary
# ============================================================
echo "=== Summary ==="
echo -e "  ${GREEN}Passed: $PASSED${NC}"
[[ $FAILED -gt 0 ]] && echo -e "  ${RED}Failed: $FAILED${NC}"
[[ $SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}Skipped: $SKIPPED${NC}"
echo ""

[[ $FAILED -gt 0 ]] && exit 1
exit 0
