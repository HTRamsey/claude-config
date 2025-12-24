#!/usr/bin/env bash
# Wrapper for compress.sh - Stack trace compression
# Usage: cat error.log | compress-stacktrace.sh
exec ~/.claude/scripts/compress.sh --type stack "$@"
