#!/usr/bin/env bash
# Wrapper for compress.sh - Build output compression
# Usage: make 2>&1 | compress-build.sh
exec ~/.claude/scripts/compress.sh --type build "$@"
