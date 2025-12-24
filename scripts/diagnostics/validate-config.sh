#!/usr/bin/env bash
# validate-config.sh - Validate Claude Code configuration consistency
# Checks hooks, agents, skills, commands, and settings for errors
#
# Usage: validate-config.sh [--fix] [--verbose]

set -e

CLAUDE_DIR="$HOME/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0
VERBOSE=false
FIX=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fix) FIX=true; shift ;;
        --verbose|-v) VERBOSE=true; shift ;;
        -h|--help)
            echo "Usage: validate-config.sh [--fix] [--verbose]"
            echo "  --fix      Attempt to fix issues (make scripts executable)"
            echo "  --verbose  Show all checks, not just failures"
            exit 0
            ;;
        *) shift ;;
    esac
done

pass() {
    [[ "$VERBOSE" == true ]] && echo -e "${GREEN}✓${NC} $1"
}
warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}
fail() {
    echo -e "${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
}
section() {
    echo -e "\n${BLUE}== $1 ==${NC}"
}

section "Settings Validation"

# Check settings.json exists and is valid JSON
if [[ ! -f "$SETTINGS" ]]; then
    fail "settings.json not found"
else
    if jq empty "$SETTINGS" 2>/dev/null; then
        pass "settings.json is valid JSON"
    else
        fail "settings.json is invalid JSON"
    fi
fi

section "Hook Validation"

# Get registered hooks from settings.json
REGISTERED_HOOKS=$(jq -r '.. | objects | select(.command?) | .command' "$SETTINGS" 2>/dev/null | grep 'hooks/' | sed 's|.*hooks/||' | sed 's|\.py.*|.py|' | sort -u)

# Check each registered hook
for hook in $REGISTERED_HOOKS; do
    hook_path="$CLAUDE_DIR/hooks/$hook"
    if [[ ! -f "$hook_path" ]]; then
        fail "Registered hook missing: $hook"
    elif ! python3 -m py_compile "$hook_path" 2>/dev/null; then
        fail "Syntax error in: $hook"
    elif [[ ! -x "$hook_path" ]]; then
        if [[ "$FIX" == true ]]; then
            chmod +x "$hook_path"
            warn "Fixed: made $hook executable"
        else
            warn "Not executable: $hook (run with --fix)"
        fi
    else
        pass "Hook OK: $hook"
    fi
done

# Check for orphan hooks (not registered in settings.json)
for hook_file in "$CLAUDE_DIR/hooks"/*.py; do
    [[ -f "$hook_file" ]] || continue
    hook=$(basename "$hook_file")
    [[ "$hook" == "hook_utils.py" ]] && continue
    [[ "$hook" == "__init__.py" ]] && continue

    if ! echo "$REGISTERED_HOOKS" | grep -q "^$hook$"; then
        warn "Orphan hook (not in settings.json): $hook"
    fi
done

section "Agent Validation"

# Check agent files
for agent in "$CLAUDE_DIR/agents"/*.md; do
    [[ -f "$agent" ]] || continue
    name=$(basename "$agent" .md)

    # Check YAML frontmatter exists
    if ! head -1 "$agent" | grep -q "^---"; then
        warn "Agent missing YAML frontmatter: $name"
    else
        pass "Agent OK: $name"
    fi
done

section "Command Validation"

# Check command files
for cmd in "$CLAUDE_DIR/commands"/*.md; do
    [[ -f "$cmd" ]] || continue
    name=$(basename "$cmd" .md)

    # Check has content beyond frontmatter
    lines=$(wc -l < "$cmd")
    if [[ $lines -lt 5 ]]; then
        warn "Command seems empty: $name ($lines lines)"
    else
        pass "Command OK: $name"
    fi
done

section "Skill Validation"

# Check skill directories
for skill_dir in "$CLAUDE_DIR/skills"/*/; do
    [[ -d "$skill_dir" ]] || continue
    name=$(basename "$skill_dir")

    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
        fail "Skill missing SKILL.md: $name"
    else
        pass "Skill OK: $name"
    fi
done

section "Script Validation"

# Check scripts are executable
for script in "$CLAUDE_DIR/scripts"/*.sh; do
    [[ -f "$script" ]] || continue
    name=$(basename "$script")

    if [[ ! -x "$script" ]]; then
        if [[ "$FIX" == true ]]; then
            chmod +x "$script"
            warn "Fixed: made $name executable"
        else
            warn "Script not executable: $name"
        fi
    elif ! bash -n "$script" 2>/dev/null; then
        fail "Syntax error in script: $name"
    else
        pass "Script OK: $name"
    fi
done

section "Python Environment"

# Check venv exists
if [[ -d "$CLAUDE_DIR/venv" ]]; then
    pass "Python venv exists"

    # Check required packages from pyproject.toml
    if [[ -f "$CLAUDE_DIR/hooks/pyproject.toml" ]]; then
        # Extract dependencies from pyproject.toml using Python for reliable parsing
        deps=$("$CLAUDE_DIR/venv/bin/python3" -c "
import tomllib
from pathlib import Path
with open(Path.home() / '.claude/hooks/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
for dep in data.get('project', {}).get('dependencies', []):
    # Extract package name (before any version specifier)
    name = dep.split('>=')[0].split('<=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
    print(name)
" 2>/dev/null)
        for pkg_name in $deps; do
            [[ -z "$pkg_name" ]] && continue
            if "$CLAUDE_DIR/venv/bin/pip" show "$pkg_name" >/dev/null 2>&1; then
                pass "Package installed: $pkg_name"
            else
                warn "Package missing: $pkg_name (run venv-setup.sh)"
            fi
        done
    fi
else
    warn "Python venv not found (run venv-setup.sh)"
fi

section "Cross-Reference Check"

# Check rules reference correct counts
HOOK_COUNT=$(ls -1 "$CLAUDE_DIR/hooks"/*.py 2>/dev/null | grep -v hook_utils | grep -v __pycache__ | wc -l)
AGENT_COUNT=$(ls -1 "$CLAUDE_DIR/agents"/*.md 2>/dev/null | wc -l)
SKILL_COUNT=$(ls -1d "$CLAUDE_DIR/skills"/*/ 2>/dev/null | wc -l)
COMMAND_COUNT=$(ls -1 "$CLAUDE_DIR/commands"/*.md 2>/dev/null | wc -l)
SCRIPT_COUNT=$(ls -1 "$CLAUDE_DIR/scripts"/*.sh 2>/dev/null | wc -l)

# Check architecture.md counts
if [[ -f "$CLAUDE_DIR/rules/architecture.md" ]]; then
    DOC_HOOKS=$(grep -oP 'Hooks \(\K\d+' "$CLAUDE_DIR/rules/architecture.md" 2>/dev/null || echo "?")
    DOC_AGENTS=$(grep -oP 'Agents \(\K\d+' "$CLAUDE_DIR/rules/architecture.md" 2>/dev/null || echo "?")
    DOC_SCRIPTS=$(grep -oP 'Scripts \(\K\d+' "$CLAUDE_DIR/rules/architecture.md" 2>/dev/null || echo "?")

    [[ "$DOC_HOOKS" == "$HOOK_COUNT" ]] && pass "Hook count matches ($HOOK_COUNT)" || warn "Hook count mismatch: docs=$DOC_HOOKS actual=$HOOK_COUNT"
    [[ "$DOC_AGENTS" == "$AGENT_COUNT" ]] && pass "Agent count matches ($AGENT_COUNT)" || warn "Agent count mismatch: docs=$DOC_AGENTS actual=$AGENT_COUNT"
    [[ "$DOC_SCRIPTS" == "$SCRIPT_COUNT" ]] && pass "Script count matches ($SCRIPT_COUNT)" || warn "Script count mismatch: docs=$DOC_SCRIPTS actual=$SCRIPT_COUNT"
fi

section "Summary"

echo ""
echo "Hooks:    $HOOK_COUNT"
echo "Agents:   $AGENT_COUNT"
echo "Skills:   $SKILL_COUNT"
echo "Commands: $COMMAND_COUNT"
echo "Scripts:  $SCRIPT_COUNT"
echo ""

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}Errors: $ERRORS${NC}"
fi
if [[ $WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
fi
if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
fi

exit $ERRORS
