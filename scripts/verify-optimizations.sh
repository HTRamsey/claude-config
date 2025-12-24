#!/usr/bin/env bash
# Verify Claude Code user-level configuration

echo "=== Claude Code User Configuration Verification ==="
echo "Date: $(date)"
echo ""

PASS=0
FAIL=0

check_file() {
    if [[ -f "$1" ]]; then
        echo "✅ $1"
        PASS=$((PASS + 1))
    else
        echo "❌ $1 (MISSING)"
        FAIL=$((FAIL + 1))
    fi
}

check_executable() {
    if [[ -x "$1" ]]; then
        echo "✅ $1 (executable)"
        PASS=$((PASS + 1))
    else
        echo "❌ $1 (not executable or missing)"
        FAIL=$((FAIL + 1))
    fi
}

check_setting() {
    local file="$1"
    local setting="$2"
    if grep -q "$setting" "$file" 2>/dev/null; then
        echo "✅ $setting in $file"
        PASS=$((PASS + 1))
    else
        echo "❌ $setting not found in $file"
        FAIL=$((FAIL + 1))
    fi
}

echo "## 1. Core Documentation"
check_file ~/.claude/CLAUDE.md
echo ""

echo "## 2. Commands"
check_file ~/.claude/commands/commit.md
check_file ~/.claude/commands/review.md
check_file ~/.claude/commands/test.md
check_file ~/.claude/commands/refactor.md
check_file ~/.claude/commands/worktree.md
check_file ~/.claude/commands/pr.md
check_file ~/.claude/commands/debug.md
echo ""

echo "## 3. Core Scripts"
check_executable ~/.claude/scripts/compress.sh
check_executable ~/.claude/scripts/health-check.sh
check_executable ~/.claude/scripts/usage-report.sh
echo ""

echo "## 4. Agents"
check_file ~/.claude/agents/code-reviewer.md
check_file ~/.claude/agents/git-expert.md
check_file ~/.claude/agents/batch-editor.md
check_file ~/.claude/agents/context-optimizer.md
check_file ~/.claude/agents/quick-lookup.md
check_file ~/.claude/agents/Explore.md
echo ""

echo "## 5. Optimization Scripts"
check_executable ~/.claude/scripts/compress-diff.sh
check_executable ~/.claude/scripts/compress-build.sh
check_executable ~/.claude/scripts/offload-grep.sh
check_executable ~/.claude/scripts/smart-preview.sh
check_executable ~/.claude/scripts/extract-signatures.sh
echo ""

echo "## 6. Settings Files"
check_file ~/.claude/settings.json
check_file ~/.claude/settings.local.json
echo ""

echo "## 7. Verify No QGC-Specific Content"
QGC_SPECIFIC_FOUND=0

if ls ~/.claude/commands/qgc-*.md 2>/dev/null | grep -q .; then
    echo "⚠️  QGC-specific commands found (should be in project .claude/)"
    QGC_SPECIFIC_FOUND=1
fi

if ls ~/.claude/agents/qgc-*.md 2>/dev/null | grep -q .; then
    echo "⚠️  QGC-specific agents found (should be in project .claude/)"
    QGC_SPECIFIC_FOUND=1
fi

if ls ~/.claude/scripts/qgc-*.sh 2>/dev/null | grep -q .; then
    echo "⚠️  QGC-specific scripts found (should be in project .claude/)"
    QGC_SPECIFIC_FOUND=1
fi

if [[ -f ~/.claude/QGC_ARCHITECTURE.md ]]; then
    echo "⚠️  QGC_ARCHITECTURE.md found (should be in project root)"
    QGC_SPECIFIC_FOUND=1
fi

if [[ $QGC_SPECIFIC_FOUND -eq 0 ]]; then
    echo "✅ No QGC-specific content in user config"
    PASS=$((PASS + 1))
else
    echo "❌ QGC-specific content should be moved to project"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "## Summary"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo "🎉 USER-LEVEL CONFIGURATION VERIFIED!"
    echo ""
    echo "User-level CLAUDE.md provides general-purpose patterns."
    echo "Project-level CLAUDE.md (in project root) provides project-specific guidance."
    echo ""
    echo "Next steps:"
    echo "1. Read: ~/.claude/CLAUDE.md"
    echo "2. Try commands: /optimize-context, /batch-review"
    echo "3. Monitor usage: ~/.claude/scripts/monitor-tokens.sh"
    exit 0
else
    echo "⚠️  Some configuration issues found"
    echo "Review the failures above"
    exit 1
fi
