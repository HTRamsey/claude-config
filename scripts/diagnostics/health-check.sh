#!/usr/bin/env bash
# Claude Code configuration health check
# Usage: health-check.sh [--cleanup]
#
# Options:
#   --cleanup    Rotate old data files (debug/, file-history/, transcript-backups/, backups/, logs)

SCRIPT_VERSION="1.2.0"

set -euo pipefail

CLEANUP=false
[[ "${1:-}" == "--cleanup" ]] && CLEANUP=true

# Data rotation function
do_cleanup() {
    echo "=== Data Rotation ==="

    # Rotate debug files > 7 days
    old_debug=$(find ~/.claude/debug -type f -mtime +7 2>/dev/null | wc -l)
    if [[ $old_debug -gt 0 ]]; then
        find ~/.claude/debug -type f -mtime +7 -delete 2>/dev/null
        echo "  debug/: deleted $old_debug files older than 7 days"
    else
        echo "  debug/: ✓ clean"
    fi

    # Rotate file-history > 30 days
    old_history=$(find ~/.claude/file-history -type f -mtime +30 2>/dev/null | wc -l)
    if [[ $old_history -gt 0 ]]; then
        find ~/.claude/file-history -type f -mtime +30 -delete 2>/dev/null
        echo "  file-history/: deleted $old_history files older than 30 days"
    else
        echo "  file-history/: ✓ clean"
    fi

    # Rotate transcript-backups: always keep only 10 most recent files
    if [[ -d ~/.claude/data/transcript-backups ]]; then
        file_count=$(find ~/.claude/data/transcript-backups -type f -name "*.jsonl" 2>/dev/null | wc -l)
        if [[ $file_count -gt 10 ]]; then
            total_size=$(du -sh ~/.claude/data/transcript-backups 2>/dev/null | cut -f1 || echo "?")
            deleted=$((file_count - 10))
            ls -1t ~/.claude/data/transcript-backups/*.jsonl 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
            echo "  transcript-backups/: trimmed to 10 files (deleted $deleted, was $total_size)"
        else
            echo "  transcript-backups/: ✓ clean ($file_count files)"
        fi
    fi

    # Rotate hook-events.jsonl if > 10MB
    if [[ -f ~/.claude/data/hook-events.jsonl ]]; then
        size=$(stat -f%z ~/.claude/data/hook-events.jsonl 2>/dev/null || stat -c%s ~/.claude/data/hook-events.jsonl 2>/dev/null || echo 0)
        if [[ $size -gt 10485760 ]]; then
            # Keep last 5000 lines
            tail -5000 ~/.claude/data/hook-events.jsonl > ~/.claude/data/hook-events.jsonl.tmp
            mv ~/.claude/data/hook-events.jsonl.tmp ~/.claude/data/hook-events.jsonl
            echo "  hook-events.jsonl: rotated (was $(numfmt --to=iec $size 2>/dev/null || echo "${size}B"))"
        else
            echo "  hook-events.jsonl: ✓ under 10MB"
        fi
    fi

    # Rotate config backups > 30 days
    if [[ -d ~/.claude/backups ]]; then
        old_backups=$(find ~/.claude/backups -type f -mtime +30 2>/dev/null | wc -l)
        if [[ $old_backups -gt 0 ]]; then
            find ~/.claude/backups -type f -mtime +30 -delete 2>/dev/null
            echo "  backups/: deleted $old_backups files older than 30 days"
        else
            echo "  backups/: ✓ clean"
        fi
    fi

    # Clean old temp files
    old_temp=$(find /tmp -maxdepth 2 -name "claude-*" -type f -mtime +7 2>/dev/null | wc -l)
    if [[ $old_temp -gt 0 ]]; then
        find /tmp -maxdepth 2 -name "claude-*" -type f -mtime +7 -delete 2>/dev/null
        echo "  /tmp/claude-*: deleted $old_temp files older than 7 days"
    else
        echo "  /tmp/: ✓ clean"
    fi

    echo ""
    echo "=== Cleanup Complete ==="
    exit 0
}

[[ "$CLEANUP" == true ]] && do_cleanup

echo "=== Claude Code Health Check ==="
echo ""

# MCP Servers
echo "## MCP Servers"
mcp_output=$(claude mcp list 2>&1)
if echo "$mcp_output" | grep -qE "✓|✗"; then
    echo "$mcp_output" | grep -E "✓|✗"
elif echo "$mcp_output" | grep -qi "no.*servers\|empty"; then
    echo "  (none configured)"
else
    echo "  (none configured)"
fi
echo ""

# Settings validation
echo "## Settings"
if python3 -m json.tool ~/.claude/settings.json > /dev/null 2>&1; then
    echo "  settings.json: ✓ valid JSON"
else
    echo "  settings.json: ✗ INVALID JSON"
fi

if [[ -f ~/.claude/settings.local.json ]]; then
    if python3 -m json.tool ~/.claude/settings.local.json > /dev/null 2>&1; then
        echo "  settings.local.json: ✓ valid JSON"
    else
        echo "  settings.local.json: ✗ INVALID JSON"
    fi
fi
echo ""

# Hooks
echo "## Hooks"
hook_errors=0
for hook in ~/.claude/hooks/*.py; do
    name=$(basename "$hook")
    # Skip utility modules (not standalone hooks)
    [[ "$name" == "hook_utils.py" ]] && continue
    if [[ ! -x "$hook" ]]; then
        echo "  $name: ✗ not executable"
        ((hook_errors++))
    elif ! python3 -m py_compile "$hook" 2>/dev/null; then
        echo "  $name: ✗ syntax error"
        ((hook_errors++))
    else
        echo "  $name: ✓ executable"
    fi
done

# Functional tests for blocking hooks
echo ""
echo "## Hook Functional Tests"

# Test dangerous_command_blocker
test_result=$(echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}' | python3 ~/.claude/hooks/dangerous_command_blocker.py 2>/dev/null)
if echo "$test_result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('hookSpecificOutput',{}).get('permissionDecision')=='deny' else 1)" 2>/dev/null; then
    echo "  dangerous_command_blocker: ✓ blocks dangerous commands"
else
    echo "  dangerous_command_blocker: ✗ FAILED to block dangerous command"
    ((hook_errors++))
fi

# Test file_protection
test_result=$(echo '{"tool_name": "Edit", "tool_input": {"file_path": "/home/user/.env"}}' | python3 ~/.claude/hooks/file_protection.py 2>/dev/null)
if echo "$test_result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('hookSpecificOutput',{}).get('permissionDecision')=='deny' else 1)" 2>/dev/null; then
    echo "  file_protection: ✓ blocks protected files"
else
    echo "  file_protection: ✗ FAILED to block .env file"
    ((hook_errors++))
fi

# Test credential_scanner (test pattern detection directly since hook requires git staged content)
fake_pat=$(printf 'gh%s_%s' 'p' 'abcdefghijklmnopqrstuvwxyz1234567890')
if python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/hooks')
from credential_scanner import scan_for_sensitive
findings = scan_for_sensitive('$fake_pat')
sys.exit(0 if findings else 1)
" 2>/dev/null; then
    echo "  credential_scanner: ✓ detects credentials"
else
    echo "  credential_scanner: ✗ FAILED to detect credentials"
    ((hook_errors++))
fi

# Test that safe commands are allowed
test_result=$(echo '{"tool_name": "Bash", "tool_input": {"command": "ls -la"}}' | python3 ~/.claude/hooks/dangerous_command_blocker.py 2>/dev/null)
if [[ -z "$test_result" ]] || echo "$test_result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('hookSpecificOutput',{}).get('permissionDecision') in ['allow',None] else 1)" 2>/dev/null; then
    echo "  dangerous_command_blocker: ✓ allows safe commands"
else
    echo "  dangerous_command_blocker: ✗ incorrectly blocking safe commands"
    ((hook_errors++))
fi

# Test precompact_save
echo "test" > /tmp/health-check-transcript.jsonl
test_result=$(echo '{"transcript_path": "/tmp/health-check-transcript.jsonl"}' | python3 ~/.claude/hooks/precompact_save.py 2>/dev/null)
if grep -q '"hook": "precompact_save"' ~/.claude/data/hook-events.jsonl 2>/dev/null; then
    echo "  precompact_save: ✓ creates backups"
else
    echo "  precompact_save: ✗ FAILED to create backup"
    ((hook_errors++))
fi
rm -f /tmp/health-check-transcript.jsonl

# Test subagent_complete
test_result=$(echo '{"subagent_type": "health-check-test", "subagent_id": "test", "stop_reason": "completed"}' | python3 ~/.claude/hooks/subagent_complete.py 2>/dev/null)
if grep -q '"hook": "subagent_complete"' ~/.claude/data/hook-events.jsonl 2>/dev/null; then
    echo "  subagent_complete: ✓ logs subagent stats"
else
    echo "  subagent_complete: ✗ FAILED to log stats"
    ((hook_errors++))
fi

# Test research_cache
echo '{"tool_name": "WebFetch", "tool_input": {"url": "https://health-check-test.example"}, "tool_result": "test"}' | python3 ~/.claude/hooks/research_cache.py >/dev/null 2>&1
test_result=$(echo '{"tool_name": "WebFetch", "tool_input": {"url": "https://health-check-test.example"}}' | python3 ~/.claude/hooks/research_cache.py 2>/dev/null)
if echo "$test_result" | grep -q "CACHE HIT"; then
    echo "  research_cache: ✓ caches and retrieves"
else
    echo "  research_cache: ✗ FAILED cache test"
    ((hook_errors++))
fi

if [[ $hook_errors -eq 0 ]]; then
    echo "  All hook tests passed ✓"
else
    echo "  ⚠ $hook_errors hook test(s) failed"
fi
echo ""

# Scripts (including subdirectories)
echo "## Scripts"
total=$(find ~/.claude/scripts -name "*.sh" -type f 2>/dev/null | wc -l)
executable=$(find ~/.claude/scripts -name "*.sh" -type f -executable 2>/dev/null | wc -l)
echo "  $executable/$total scripts executable"
echo "  Subdirectories: search/, compress/, smart/, analysis/, git/, queue/, diagnostics/, automation/, lib/"

# Manifest validation
if [[ -f ~/.claude/scripts/manifest.json ]]; then
    echo "  manifest.json: ✓ present"
    if python3 -m json.tool ~/.claude/scripts/manifest.json > /dev/null 2>&1; then
        echo "  manifest.json: ✓ valid JSON"
    else
        echo "  manifest.json: ✗ INVALID JSON"
    fi
else
    echo "  manifest.json: ✗ MISSING"
fi
echo ""

# Dependencies from manifest - use sorted array for consistent output
echo "## Dependencies"

# Define dependencies as sorted list for predictable output
dep_list=(
    "ast-grep:command -v ast-grep || command -v sg || test -x ~/.cargo/bin/ast-grep"
    "bat:command -v bat || command -v batcat || test -x ~/.cargo/bin/bat"
    "curlie:command -v curlie || test -x ~/go/bin/curlie"
    "delta:command -v delta"
    "difft:command -v difft || test -x ~/.cargo/bin/difft"
    "dust:command -v dust || test -x ~/.cargo/bin/dust"
    "eza:command -v eza"
    "fd:command -v fd || command -v fdfind || test -x ~/.cargo/bin/fd"
    "fzf:command -v fzf"
    "git:command -v git"
    "gron:command -v gron"
    "htmlq:command -v htmlq || test -x ~/.cargo/bin/htmlq"
    "jq:command -v jq"
    "rg:command -v rg || test -x ~/.cargo/bin/rg"
    "sd:command -v sd"
    "tldr:command -v tldr"
    "tokei:command -v tokei || test -x ~/.cargo/bin/tokei"
    "xh:command -v xh || test -x ~/.cargo/bin/xh"
    "yq:command -v yq || test -x ~/.local/bin/yq"
    "zoxide:command -v zoxide"
)

missing_deps=()
for entry in "${dep_list[@]}"; do
    dep="${entry%%:*}"
    check="${entry#*:}"
    if eval "$check" &>/dev/null; then
        echo "  $dep: ✓"
    else
        echo "  $dep: ✗ missing"
        missing_deps+=("$dep")
    fi
done

if [[ ${#missing_deps[@]} -gt 0 ]]; then
    echo ""
    echo "  Install missing: cargo install fd-find bat eza git-delta sd du-dust difftastic tokei ast-grep zoxide"
fi
echo ""

# Rules
echo "## Rules"
echo "  $(ls ~/.claude/rules/*.md 2>/dev/null | wc -l) rule files loaded"
echo ""

# Commands
echo "## Commands"
echo "  $(ls ~/.claude/commands/*.md 2>/dev/null | wc -l) custom commands"
echo ""

# Statusline
echo "## Statusline"
if [[ -x ~/.claude/scripts/statusline.sh ]]; then
    echo "  statusline.sh: ✓ executable"
else
    echo "  statusline.sh: ✗ not executable or missing"
fi
echo ""

# Security checks
echo "## Security"
# Check if blocking hooks use proper JSON format (permissionDecision: deny)
if grep -q '"permissionDecision": "deny"' ~/.claude/hooks/credential_scanner.py 2>/dev/null; then
    echo "  credential_scanner: ✓ blocking enabled (JSON format)"
else
    echo "  credential_scanner: ⚠ may not block properly"
fi

if grep -q '"permissionDecision": "deny"' ~/.claude/hooks/dangerous_command_blocker.py 2>/dev/null; then
    echo "  dangerous_command_blocker: ✓ blocking enabled (JSON format)"
else
    echo "  dangerous_command_blocker: ⚠ may not block properly"
fi

if grep -q '"permissionDecision": "deny"' ~/.claude/hooks/file_protection.py 2>/dev/null; then
    echo "  file_protection: ✓ blocking enabled (JSON format)"
else
    echo "  file_protection: ⚠ may not block properly"
fi

# Check for deprecated sys.exit(2) usage
deprecated_hooks=0
for hook in ~/.claude/hooks/*.py; do
    if grep -q "sys.exit(2)" "$hook" 2>/dev/null; then
        ((deprecated_hooks++))
    fi
done
if [[ $deprecated_hooks -gt 0 ]]; then
    echo "  ⚠ $deprecated_hooks hook(s) using deprecated sys.exit(2) - may cause 'No stderr output' errors"
else
    echo "  hook format: ✓ all hooks use proper JSON format"
fi

# Check hook permissions
insecure_hooks=$(find ~/.claude/hooks -name "*.py" -perm /go+w 2>/dev/null | wc -l)
if [[ $insecure_hooks -eq 0 ]]; then
    echo "  hook permissions: ✓ secure"
else
    echo "  hook permissions: ⚠ $insecure_hooks files with group/other write"
fi
echo ""

# Disk usage / cleanup
echo "## Disk Usage"
debug_size=$(du -sh ~/.claude/debug 2>/dev/null | cut -f1)
history_size=$(du -sh ~/.claude/file-history 2>/dev/null | cut -f1)
echo "  debug/: $debug_size"
echo "  file-history/: $history_size"

# Old temp files (disable pipefail for this section)
set +o pipefail
old_temp=$(find /tmp -maxdepth 2 -name "claude-*" -type f -mtime +7 2>/dev/null | wc -l 2>/dev/null | tr -d '[:space:]' || echo "0")
[[ -z "$old_temp" ]] && old_temp=0
if [[ "$old_temp" == "0" ]]; then
    echo "  temp files: ✓ clean"
else
    echo "  temp files: ⚠ $old_temp files older than 7 days in /tmp"
fi

old_debug=$(find ~/.claude/debug -type f -mtime +7 2>/dev/null | wc -l 2>/dev/null | tr -d '[:space:]' || echo "0")
[[ -z "$old_debug" ]] && old_debug=0
if [[ "$old_debug" != "0" ]]; then
    echo "  debug cleanup: ⚠ $old_debug files older than 7 days"
fi
set -o pipefail
echo ""

echo "=== Health Check Complete ==="
