#!/usr/bin/env bash
# Wrapper for compress.sh - List filtering
# Usage: compress-list.sh '<list>' '<pattern>' [limit]
exec ~/.claude/scripts/compress.sh --type list "$@"
