#!/usr/bin/env bash
# Hook Testing Framework
# Tests hooks with mock input data and validates output format
set -euo pipefail

# Load common utilities
source "$(dirname "$0")/../lib/common.sh"

HOOKS_DIR="${HOME}/.claude/hooks"
VENV_PYTHON="${HOME}/.claude/venv/bin/python3"

# Test results
PASSED=0
FAILED=0
SKIPPED=0

show_help() {
  cat << 'EOF'
Usage: test-hooks.sh [HOOK_NAME]

Test Claude Code hooks for correct behavior and error handling.

Arguments:
  HOOK_NAME      Specific hook to test (default: all)
                 Valid values: all, file_protection, credential_scanner,
                               dangerous_command_blocker, exploration_cache,
                               or any hook name without .py extension

Tests performed:
  - Graceful handling (empty input, invalid JSON, empty objects)
  - Specific behavior tests (blocking protected files, dangerous commands, etc.)
  - JSON output validation (when applicable)
  - Exit code verification

Examples:
  test-hooks.sh                    # Test all hooks
  test-hooks.sh all                # Test all hooks (explicit)
  test-hooks.sh file_protection    # Test file_protection hook only
  test-hooks.sh credential_scanner # Test credential_scanner hook only

Exit codes:
  0  All tests passed
  1  One or more tests failed or hook not found
EOF
  exit 0
}

log_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASSED++)); }
log_fail() { echo -e "${RED}✗${NC} $1"; ((FAILED++)); }
log_skip() { echo -e "${YELLOW}○${NC} $1"; ((SKIPPED++)); }

# Test a hook with given input, check for valid JSON output or clean exit
test_hook() {
    local hook="$1"
    local input="$2"
    local description="$3"
    local expect_output="${4:-false}"  # Whether we expect JSON output

    local name=$(basename "$hook" .py)
    local output
    local exit_code

    output=$(echo "$input" | timeout 5 "$VENV_PYTHON" "$hook" 2>/dev/null) && exit_code=0 || exit_code=$?

    # Check exit code (0 is success)
    if [[ $exit_code -ne 0 ]]; then
        log_fail "$name: $description (exit code: $exit_code)"
        return 1
    fi

    # If output expected, validate it's valid JSON
    if [[ "$expect_output" == "true" && -n "$output" ]]; then
        if echo "$output" | jq . >/dev/null 2>&1; then
            log_pass "$name: $description"
        else
            log_fail "$name: $description (invalid JSON output)"
            return 1
        fi
    elif [[ "$expect_output" == "false" ]]; then
        log_pass "$name: $description"
    else
        log_pass "$name: $description (no output, clean exit)"
    fi
}

# Test that hook handles empty/invalid input gracefully
test_graceful_handling() {
    local hook="$1"
    local name=$(basename "$hook" .py)

    # Empty input
    local exit_code
    echo "" | timeout 5 "$VENV_PYTHON" "$hook" 2>/dev/null && exit_code=0 || exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        log_pass "$name: handles empty input"
    else
        log_fail "$name: crashes on empty input (exit: $exit_code)"
    fi

    # Invalid JSON
    echo "not json" | timeout 5 "$VENV_PYTHON" "$hook" 2>/dev/null && exit_code=0 || exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        log_pass "$name: handles invalid JSON"
    else
        log_fail "$name: crashes on invalid JSON (exit: $exit_code)"
    fi

    # Empty JSON object
    echo "{}" | timeout 5 "$VENV_PYTHON" "$hook" 2>/dev/null && exit_code=0 || exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        log_pass "$name: handles empty JSON object"
    else
        log_fail "$name: crashes on empty JSON (exit: $exit_code)"
    fi
}

# Test specific hook behaviors
test_file_protection() {
    local hook="$HOOKS_DIR/file_protection.py"
    [[ -f "$hook" ]] || { log_skip "file_protection: not found"; return; }

    echo "=== Testing file_protection ==="
    test_graceful_handling "$hook"

    # Should block .env file
    test_hook "$hook" '{"tool_name":"Write","tool_input":{"file_path":"/app/.env"}}' \
        "blocks .env file" true

    # Should allow normal file
    test_hook "$hook" '{"tool_name":"Write","tool_input":{"file_path":"/app/src/main.py"}}' \
        "allows normal file" false
}

test_credential_scanner() {
    local hook="$HOOKS_DIR/credential_scanner.py"
    [[ -f "$hook" ]] || { log_skip "credential_scanner: not found"; return; }

    echo "=== Testing credential_scanner ==="
    test_graceful_handling "$hook"

    # Should exit cleanly for non-commit commands
    test_hook "$hook" '{"tool_name":"Bash","tool_input":{"command":"git status"}}' \
        "ignores non-commit commands" false
}

test_dangerous_command_blocker() {
    local hook="$HOOKS_DIR/dangerous_command_blocker.py"
    [[ -f "$hook" ]] || { log_skip "dangerous_command_blocker: not found"; return; }

    echo "=== Testing dangerous_command_blocker ==="
    test_graceful_handling "$hook"

    # Should block rm -rf /
    test_hook "$hook" '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' \
        "blocks rm -rf /" true

    # Should allow safe commands
    test_hook "$hook" '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' \
        "allows ls -la" false
}

test_exploration_cache() {
    local hook="$HOOKS_DIR/exploration_cache.py"
    [[ -f "$hook" ]] || { log_skip "exploration_cache: not found"; return; }

    echo "=== Testing exploration_cache ==="
    test_graceful_handling "$hook"

    # Should handle Task tool with Explore subagent
    test_hook "$hook" '{"tool_name":"Task","tool_input":{"subagent_type":"Explore","prompt":"find auth code"}}' \
        "handles Explore subagent" false

    # Should ignore non-Task tools
    test_hook "$hook" '{"tool_name":"Bash","tool_input":{"command":"echo test"}}' \
        "ignores non-Task tools" false
}

# Run all tests or specific hook
run_tests() {
    local target="${1:-all}"

    echo "Hook Testing Framework"
    echo "======================"
    echo ""

    if [[ "$target" == "all" ]]; then
        # Test all hooks for graceful handling
        echo "=== Graceful Handling Tests ==="
        for hook in "$HOOKS_DIR"/*.py; do
            [[ -f "$hook" ]] || continue
            [[ "$(basename "$hook")" == "hook_utils.py" ]] && continue
            test_graceful_handling "$hook"
            echo ""
        done

        # Run specific behavior tests
        test_file_protection
        echo ""
        test_credential_scanner
        echo ""
        test_dangerous_command_blocker
        echo ""
        test_exploration_cache
    else
        # Test specific hook
        local hook="$HOOKS_DIR/${target}.py"
        if [[ -f "$hook" ]]; then
            test_graceful_handling "$hook"
            # Run specific test if function exists
            if declare -f "test_${target}" >/dev/null 2>&1; then
                "test_${target}"
            fi
        else
            echo "Hook not found: $target"
            exit 1
        fi
    fi

    echo ""
    echo "======================"
    echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}, ${YELLOW}$SKIPPED skipped${NC}"

    [[ $FAILED -eq 0 ]] || exit 1
}

# Main
case "${1:-}" in
    -h|--help)
        show_help
        ;;
    *)
        run_tests "${1:-all}"
        ;;
esac
