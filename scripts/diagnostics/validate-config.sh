#!/usr/bin/env bash
# validate-config.sh - Validate Claude Code configuration consistency
# Checks hooks, agents, skills, commands, and settings for errors
#
# Usage: validate-config.sh [--fix] [--verbose]

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

CLAUDE_DIR="$HOME/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"

# Colors already exported by common.sh

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
    [[ "$VERBOSE" == true ]] && echo -e "${GREEN}✓${NC} $1" || true
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

        # Check required top-level fields
        for field in "permissions" "env" "hooks"; do
            if jq -e ".$field" "$SETTINGS" >/dev/null 2>&1; then
                pass "settings.json has '$field' section"
            else
                warn "settings.json missing '$field' section"
            fi
        done

        # Validate hook event names
        VALID_EVENTS="PreToolUse PostToolUse Stop Notification UserPromptSubmit PermissionRequest SessionStart SessionEnd SubagentStart SubagentStop PreCompact"
        CONFIGURED_EVENTS=$(jq -r '.hooks | keys[]' "$SETTINGS" 2>/dev/null)
        for event in $CONFIGURED_EVENTS; do
            if echo "$VALID_EVENTS" | grep -qw "$event"; then
                pass "Valid event: $event"
            else
                warn "Unknown hook event: $event"
            fi
        done

        # Check hook timeout values
        TIMEOUTS=$(jq -r '.. | objects | select(.timeout?) | .timeout' "$SETTINGS" 2>/dev/null)
        for timeout in $TIMEOUTS; do
            if [[ "$timeout" -gt 30 ]]; then
                warn "Hook timeout >30s may cause delays: ${timeout}s"
            fi
        done
    else
        fail "settings.json is invalid JSON"
    fi
fi

section "Hook Validation"

# Get registered hooks from settings.json
# Extract hook filenames, handling both .py and .sh extensions
REGISTERED_HOOKS=$(jq -r '.. | objects | select(.command?) | .command' "$SETTINGS" 2>/dev/null | \
    grep 'hooks/' | \
    sed 's|.*hooks/||' | \
    sed -E 's/(\.py|\.sh).*/\1/' | \
    sort -u)

# Check each registered hook
for hook in $REGISTERED_HOOKS; do
    hook_path="$CLAUDE_DIR/hooks/$hook"
    if [[ ! -f "$hook_path" ]]; then
        fail "Registered hook missing: $hook"
    else
        # Check syntax based on file extension
        syntax_ok=false
        if [[ "$hook" == *.py ]]; then
            python3 -m py_compile "$hook_path" 2>/dev/null && syntax_ok=true
        elif [[ "$hook" == *.sh ]]; then
            bash -n "$hook_path" 2>/dev/null && syntax_ok=true
        else
            syntax_ok=true  # Unknown extension, skip syntax check
        fi

        if [[ "$syntax_ok" != true ]]; then
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
    fi
done

# Check for orphan hooks (not registered in settings.json)
for hook_file in "$CLAUDE_DIR/hooks"/*.py; do
    [[ -f "$hook_file" ]] || continue
    hook=$(basename "$hook_file")
    [[ "$hook" == "hook_utils.py" ]] && continue
    [[ "$hook" == "__init__.py" ]] && continue
    [[ "$hook" == "__pycache__" ]] && continue

    if ! echo "$REGISTERED_HOOKS" | grep -q "^$hook$"; then
        warn "Orphan hook (not in settings.json): $hook"
    fi
done

# Check dispatcher handler references
section "Dispatcher Validation"

for dispatcher in "$CLAUDE_DIR/hooks"/*_dispatcher.py; do
    [[ -f "$dispatcher" ]] || continue
    dname=$(basename "$dispatcher" .py)

    # Extract handler names from ALL_HANDLERS list (looking for the array definition)
    handlers=$(grep -A5 "^ALL_HANDLERS = \[" "$dispatcher" 2>/dev/null | grep -oP '"[a-z_]+"' | tr -d '"' || true)
    handler_count=0
    handler_ok=0
    for handler in $handlers; do
        [[ -z "$handler" ]] && continue
        handler_count=$((handler_count + 1))
        # Check if handler has a corresponding .py file
        if [[ -f "$CLAUDE_DIR/hooks/$handler.py" ]]; then
            handler_ok=$((handler_ok + 1))
            [[ "$VERBOSE" == true ]] && pass "$dname handler: $handler" || true
        else
            warn "$dname references missing handler: $handler"
        fi
    done
    if [[ $handler_count -gt 0 && $handler_ok -eq $handler_count ]]; then
        pass "$dname: all $handler_count handlers found"
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
    [[ "$name" == "archive" ]] && continue  # Skip archive meta-directory

    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
        fail "Skill missing SKILL.md: $name"
    else
        pass "Skill OK: $name"
    fi
done

section "Script Validation"

# Check scripts are executable (all subdirectories)
SCRIPT_ERRORS=0
SCRIPT_OK=0
while IFS= read -r script; do
    [[ -f "$script" ]] || continue
    rel_path="${script#$CLAUDE_DIR/scripts/}"

    if [[ ! -x "$script" ]]; then
        if [[ "$FIX" == true ]]; then
            chmod +x "$script"
            warn "Fixed: made $rel_path executable"
        else
            warn "Script not executable: $rel_path"
        fi
    elif ! bash -n "$script" 2>/dev/null; then
        fail "Syntax error in script: $rel_path"
        SCRIPT_ERRORS=$((SCRIPT_ERRORS + 1))
    else
        SCRIPT_OK=$((SCRIPT_OK + 1))
        [[ "$VERBOSE" == true ]] && pass "Script OK: $rel_path" || true
    fi
done < <(find "$CLAUDE_DIR/scripts" -name "*.sh" -type f 2>/dev/null)

if [[ $SCRIPT_ERRORS -eq 0 ]]; then
    pass "All $SCRIPT_OK scripts have valid syntax"
fi

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
HOOK_COUNT=$(find "$CLAUDE_DIR/hooks" -maxdepth 1 -name "*.py" -type f 2>/dev/null | grep -v hook_utils | grep -v __pycache__ | grep -v __init__ | wc -l)
AGENT_COUNT=$(find "$CLAUDE_DIR/agents" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
SKILL_COUNT=$(find "$CLAUDE_DIR/skills" -maxdepth 1 -type d ! -name archive 2>/dev/null | tail -n +2 | wc -l)
COMMAND_COUNT=$(find "$CLAUDE_DIR/commands" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
SCRIPT_COUNT=$(find "$CLAUDE_DIR/scripts" -name "*.sh" -type f 2>/dev/null | wc -l)

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
