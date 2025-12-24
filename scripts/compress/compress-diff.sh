#!/usr/bin/env bash
# Wrapper for compress.sh - Git diff compression
# Usage: compress-diff.sh [ref]
exec ~/.claude/scripts/compress/compress.sh --type diff "$@"
