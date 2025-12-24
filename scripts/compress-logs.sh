#!/usr/bin/env bash
# Wrapper for compress.sh - Log compression
# Usage: compress-logs.sh '<logs>' [max_lines]
exec ~/.claude/scripts/compress.sh --type logs "$@"
