#!/usr/bin/env bash
# Usage Report - Shows skill/agent/command usage statistics
# Reads from ~/.claude/data/usage-stats.json

set -e

USAGE_FILE="$HOME/.claude/data/usage-stats.json"

if [[ ! -f "$USAGE_FILE" ]]; then
    echo "No usage data yet. Run some skills/agents/commands first."
    echo ""
    echo "Usage tracking is enabled via the usage_tracker.py hook."
    exit 0
fi

echo "=== Claude Code Usage Report ==="
echo "Data from: $USAGE_FILE"
echo ""

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Install jq for formatted output: sudo apt install jq"
    cat "$USAGE_FILE"
    exit 0
fi

echo "--- Agents (by usage count) ---"
jq -r '.agents | to_entries | sort_by(-.value.count) | .[] | "\(.value.count)\t\(.key)\t(last: \(.value.last_used // "never" | split("T")[0]))"' "$USAGE_FILE" 2>/dev/null || echo "No agent data"
echo ""

echo "--- Skills (by usage count) ---"
jq -r '.skills | to_entries | sort_by(-.value.count) | .[] | "\(.value.count)\t\(.key)\t(last: \(.value.last_used // "never" | split("T")[0]))"' "$USAGE_FILE" 2>/dev/null || echo "No skill data"
echo ""

echo "--- Commands (by usage count) ---"
jq -r '.commands | to_entries | sort_by(-.value.count) | .[] | "\(.value.count)\t\(.key)\t(last: \(.value.last_used // "never" | split("T")[0]))"' "$USAGE_FILE" 2>/dev/null || echo "No command data"
echo ""

echo "--- Daily Totals (last 7 days) ---"
jq -r '.daily | to_entries | sort_by(.key) | reverse | .[0:7] | .[] | "\(.key)\tagents:\(.value.agents // 0)\tskills:\(.value.skills // 0)\tcmds:\(.value.commands // 0)"' "$USAGE_FILE" 2>/dev/null || echo "No daily data"
echo ""

echo "--- Never Used ---"
echo "Agents defined but never used:"
comm -23 <(ls -1 ~/.claude/agents/*.md 2>/dev/null | xargs -I{} basename {} .md | sort) \
         <(jq -r '.agents | keys[]' "$USAGE_FILE" 2>/dev/null | sort) 2>/dev/null | head -10 || echo "  (tracking not started)"

echo ""
echo "Skills defined but never used:"
comm -23 <(ls -1d ~/.claude/skills/*/ 2>/dev/null | xargs -I{} basename {} | sort) \
         <(jq -r '.skills | keys[]' "$USAGE_FILE" 2>/dev/null | sort) 2>/dev/null | head -10 || echo "  (tracking not started)"

echo ""
echo "Commands defined but never used:"
comm -23 <(ls -1 ~/.claude/commands/*.md 2>/dev/null | xargs -I{} basename {} .md | sort) \
         <(jq -r '.commands | keys[]' "$USAGE_FILE" 2>/dev/null | sort) 2>/dev/null | head -10 || echo "  (tracking not started)"

echo ""
echo "--- Cache Statistics ---"
CACHE_FILE="$HOME/.claude/data/exploration-cache.json"
if [[ -f "$CACHE_FILE" ]] && command -v jq &>/dev/null; then
    CACHE_SIZE=$(jq 'length' "$CACHE_FILE" 2>/dev/null || echo 0)
    CACHE_BYTES=$(wc -c < "$CACHE_FILE" 2>/dev/null || echo 0)
    echo "Exploration cache entries: $CACHE_SIZE"
    echo "Cache file size: $((CACHE_BYTES / 1024))KB"

    # Show oldest and newest entries if cache has data
    if [[ "$CACHE_SIZE" -gt 0 ]]; then
        OLDEST=$(jq -r 'to_entries | sort_by(.value.timestamp) | .[0].value.timestamp // "unknown"' "$CACHE_FILE" 2>/dev/null | cut -d'T' -f1)
        NEWEST=$(jq -r 'to_entries | sort_by(.value.timestamp) | .[-1].value.timestamp // "unknown"' "$CACHE_FILE" 2>/dev/null | cut -d'T' -f1)
        echo "Date range: $OLDEST to $NEWEST"
    fi
else
    echo "No exploration cache data"
fi

echo ""
echo "--- Token Usage ---"
TOKEN_FILE="$HOME/.claude/data/token-usage.json"
if [[ -f "$TOKEN_FILE" ]] && command -v jq &>/dev/null; then
    TODAY=$(date +%Y-%m-%d)
    TODAY_TOKENS=$(jq -r ".daily.\"$TODAY\".total // 0" "$TOKEN_FILE" 2>/dev/null)
    TOTAL_TOKENS=$(jq -r '.total // 0' "$TOKEN_FILE" 2>/dev/null)
    echo "Today's tokens: $TODAY_TOKENS"
    echo "All-time tokens: $TOTAL_TOKENS"
else
    echo "No token usage data"
fi

echo ""
echo "--- Session Info ---"
SESSIONS=$(find "$HOME/.claude/projects" -name "*.jsonl" -mtime -7 2>/dev/null | wc -l)
echo "Sessions (last 7 days): $SESSIONS"

BACKUPS=$(ls -1 "$HOME/.claude/data/transcript-backups"/*.jsonl 2>/dev/null | wc -l)
echo "Transcript backups: $BACKUPS"
