#!/usr/bin/env bash
# smart-tree.sh - Tree view wrapper (calls smart-ls.sh with depth)
# Usage: smart-tree.sh [path] [depth] [pattern]
#
# This is now a thin wrapper around smart-ls.sh
# Default depth is 3 (vs smart-ls.sh default of 1)

path="${1:-.}"
depth="${2:-3}"
pattern="${3:-}"

exec "$HOME/.claude/scripts/smart-ls.sh" "$path" "$depth" "$pattern"
