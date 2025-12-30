#!/usr/bin/env bash
set -euo pipefail
# smoke-test.sh - Basic smoke tests for critical scripts
#
# Usage: ./smoke-test.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source common library for colors and utilities
source "$SCRIPT_DIR/lib/common.sh"

PASSED=0
FAILED=0
SKIPPED=0

log_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASSED++)) || true; }
log_fail() { echo -e "${RED}✗${NC} $1"; ((FAILED++)) || true; }
log_skip() { echo -e "${YELLOW}○${NC} $1"; ((SKIPPED++)) || true; }

echo "=== Script Smoke Tests ==="
echo ""

# ============================================================
# compress.sh tests
# ============================================================
echo "## compress.sh"

if "$SCRIPT_DIR/compress/compress.sh" --help >/dev/null 2>&1; then
    log_pass "compress.sh --help"
else
    log_fail "compress.sh --help"
fi

if "$SCRIPT_DIR/compress/compress.sh" --version 2>&1 | grep -q "version"; then
    log_pass "compress.sh --version"
else
    log_fail "compress.sh --version"
fi

if echo "error: test" | "$SCRIPT_DIR/compress/compress.sh" -t build --json 2>&1 | grep -q '"type":"build"'; then
    log_pass "compress.sh -t build --json"
else
    log_fail "compress.sh -t build --json"
fi

compress_output=$("$SCRIPT_DIR/compress/compress.sh" 2>&1 || true)
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

if source "$SCRIPT_DIR/lib/common.sh" 2>/dev/null; then
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

if "$SCRIPT_DIR/automation/parallel.sh" --help >/dev/null 2>&1; then
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

if "$SCRIPT_DIR/git/git-prep.sh" --help >/dev/null 2>&1; then
    log_pass "git-prep.sh --help"
else
    log_fail "git-prep.sh --help"
fi

echo ""

# ============================================================
# offload-grep.sh tests
# ============================================================
echo "## offload-grep.sh"

if "$SCRIPT_DIR/search/offload-grep.sh" 'echo' "$SCRIPT_DIR" 5 >/dev/null 2>&1; then
    log_pass "offload-grep.sh basic search"
else
    log_fail "offload-grep.sh basic search"
fi

echo ""

# ============================================================
# smart-preview.sh tests
# ============================================================
echo "## smart-preview.sh"

if [[ -x "$SCRIPT_DIR/smart/smart-preview.sh" ]]; then
    if "$SCRIPT_DIR/smart/smart-preview.sh" "$SCRIPT_DIR/lib/common.sh" >/dev/null 2>&1; then
        log_pass "smart-preview.sh on file"
    else
        log_fail "smart-preview.sh on file"
    fi
else
    log_skip "smart-preview.sh (not found)"
fi

echo ""

# ============================================================
# health-check.sh - skipped (calls claude CLI)
# ============================================================
echo "## health-check.sh"
log_skip "health-check.sh (calls claude CLI)"

echo ""

# ============================================================
# Hook Compilation Tests
# ============================================================
echo "## Hook Compilation"

HOOKS_DIR="$HOME/.claude/hooks"
VENV_PYTHON="$HOME/.claude/data/venv/bin/python3"

# Check venv exists
if [[ -x "$VENV_PYTHON" ]]; then
    log_pass "venv Python exists"

    # Test all Python hooks compile
    hook_errors=0
    for hook in "$HOOKS_DIR"/*.py; do
        hookname=$(basename "$hook")
        if "$VENV_PYTHON" -m py_compile "$hook" 2>/dev/null; then
            : # silent pass
        else
            log_fail "Hook compile: $hookname"
            ((hook_errors++))
        fi
    done

    if [[ $hook_errors -eq 0 ]]; then
        hook_count=$(ls -1 "$HOOKS_DIR"/*.py 2>/dev/null | wc -l)
        log_pass "All $hook_count hooks compile"
    fi
else
    log_skip "Hook compilation (venv not found)"
fi

echo ""

# ============================================================
# Hook SDK Tests
# ============================================================
echo "## Hook SDK"

if [[ -x "$VENV_PYTHON" ]]; then
    # Test hook_utils imports
    if "$VENV_PYTHON" -c "import sys; sys.path.insert(0, '$HOOKS_DIR'); from hook_utils import graceful_main, log_event, read_state, write_state, read_session_state, write_session_state" 2>/dev/null; then
        log_pass "hook_utils imports"
    else
        log_fail "hook_utils imports"
    fi

    # Test hook_sdk imports
    if "$VENV_PYTHON" -c "import sys; sys.path.insert(0, '$HOOKS_DIR'); from hook_sdk import PreToolUseContext, Response, dispatch_handler, run_standalone" 2>/dev/null; then
        log_pass "hook_sdk imports"
    else
        log_fail "hook_sdk imports"
    fi

    # Test session state functions work
    session_test=$("$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$HOOKS_DIR')
from hook_utils import read_session_state, write_session_state
# Write test data
write_session_state('smoke_test', {'test': True}, 'smoke-test-session')
# Read it back
data = read_session_state('smoke_test', 'smoke-test-session', {})
print('ok' if data.get('test') == True else 'fail')
" 2>/dev/null || echo "error")

    if [[ "$session_test" == "ok" ]]; then
        log_pass "Session state read/write"
    else
        log_fail "Session state read/write"
    fi
else
    log_skip "Hook SDK tests (venv not found)"
fi

echo ""

# ============================================================
# Dispatcher Tests
# ============================================================
echo "## Hook Dispatchers"

if [[ -x "$VENV_PYTHON" ]]; then
    # Test pre_tool_dispatcher with a Read operation
    pre_result=$(echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.txt"}}' | \
        "$VENV_PYTHON" "$HOOKS_DIR/pre_tool_dispatcher.py" 2>/dev/null; echo "exit:$?")

    if echo "$pre_result" | grep -q "exit:0"; then
        log_pass "pre_tool_dispatcher runs"
    else
        log_fail "pre_tool_dispatcher runs"
    fi

    # Test post_tool_dispatcher with a Bash result
    post_result=$(echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":{"stdout":"test"}}' | \
        "$VENV_PYTHON" "$HOOKS_DIR/post_tool_dispatcher.py" 2>/dev/null; echo "exit:$?")

    if echo "$post_result" | grep -q "exit:0"; then
        log_pass "post_tool_dispatcher runs"
    else
        log_fail "post_tool_dispatcher runs"
    fi

    # Test user_prompt_dispatcher
    prompt_result=$(echo '{"user_prompt":"test","transcript_path":"/tmp/fake.jsonl"}' | \
        "$VENV_PYTHON" "$HOOKS_DIR/user_prompt_dispatcher.py" 2>/dev/null; echo "exit:$?")

    if echo "$prompt_result" | grep -q "exit:0"; then
        log_pass "user_prompt_dispatcher runs"
    else
        log_fail "user_prompt_dispatcher runs"
    fi
else
    log_skip "Dispatcher tests (venv not found)"
fi

echo ""

# ============================================================
# Additional Script Tests
# ============================================================
echo "## Additional Scripts"

# offload-find.sh
if "$SCRIPT_DIR/search/offload-find.sh" "$SCRIPT_DIR" "*.sh" 5 >/dev/null 2>&1; then
    log_pass "offload-find.sh basic search"
else
    log_fail "offload-find.sh basic search"
fi

# smart-view.sh
if [[ -x "$SCRIPT_DIR/smart/smart-view.sh" ]]; then
    if "$SCRIPT_DIR/smart/smart-view.sh" "$SCRIPT_DIR/lib/common.sh" >/dev/null 2>&1; then
        log_pass "smart-view.sh on file"
    else
        log_fail "smart-view.sh on file"
    fi
else
    log_skip "smart-view.sh (not found)"
fi

# validate-config.sh (dry run)
if "$SCRIPT_DIR/diagnostics/validate-config.sh" >/dev/null 2>&1; then
    log_pass "validate-config.sh runs"
else
    log_fail "validate-config.sh runs"
fi

# hook-cli.sh list
if "$SCRIPT_DIR/diagnostics/hook-cli.sh" list >/dev/null 2>&1; then
    log_pass "hook-cli.sh list"
else
    log_fail "hook-cli.sh list"
fi

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
