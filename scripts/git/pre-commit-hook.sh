#!/usr/bin/env bash
# Git pre-commit hook for Claude Code configuration
#
# INSTALLATION:
#   cp ~/.claude/scripts/git/pre-commit-hook.sh ~/.claude/.git/hooks/pre-commit
#   chmod +x ~/.claude/.git/hooks/pre-commit
#
# Or use a symlink:
#   ln -sf ~/.claude/scripts/git/pre-commit-hook.sh ~/.claude/.git/hooks/pre-commit
#
# Runs credential scanner on staged changes

set -euo pipefail

HOOK_DIR="$HOME/.claude/hooks"
SCANNER="$HOOK_DIR/credential_scanner.py"

# Skip if scanner doesn't exist
if [[ ! -f "$SCANNER" ]]; then
    echo "Warning: credential_scanner.py not found, skipping pre-commit check"
    exit 0
fi

# Get staged content
staged_diff=$(git diff --cached --diff-filter=ACMR 2>/dev/null || true)

if [[ -z "$staged_diff" ]]; then
    exit 0
fi

# Run credential scanner
# The scanner expects JSON input with tool_name and tool_input
input_json=$(cat <<EOF
{
    "tool_name": "Bash",
    "tool_input": {
        "command": "git commit"
    }
}
EOF
)

result=$(echo "$input_json" | python3 "$SCANNER" 2>/dev/null || true)

# Check if scanner blocked the commit
if echo "$result" | grep -q '"permissionDecision": "deny"'; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  COMMIT BLOCKED: Potential credentials detected in staged files  ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    # Extract and display the reason
    reason=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('hookSpecificOutput',{}).get('permissionDecisionReason','Unknown reason'))" 2>/dev/null || echo "Check staged files for secrets")
    echo "$reason"
    echo ""
    echo "To bypass this check (use with caution):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
fi

exit 0
