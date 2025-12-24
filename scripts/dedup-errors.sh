#!/usr/bin/env bash
# Wrapper for compress.sh - Error deduplication
# Usage: cat errors.log | dedup-errors.sh
exec ~/.claude/scripts/compress.sh --type errors "$@"
