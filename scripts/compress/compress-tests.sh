#!/usr/bin/env bash
# Wrapper for compress.sh - Test output compression
# Usage: pytest -v 2>&1 | compress-tests.sh
exec ~/.claude/scripts/compress/compress.sh --type tests "$@"
