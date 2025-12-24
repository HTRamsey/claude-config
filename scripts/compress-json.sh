#!/usr/bin/env bash
# Wrapper for compress.sh - JSON field extraction
# Usage: compress-json.sh '<json>' 'field1,field2'
exec ~/.claude/scripts/compress.sh --type json "$@"
