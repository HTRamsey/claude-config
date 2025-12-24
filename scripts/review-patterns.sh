#!/bin/bash
# Code Review Detection Patterns
# Reference for code-reviewer agent

case "$1" in
  security)
    cat << 'EOF'
# Hardcoded secrets
Grep: '(?i)(password|secret|api.?key|token)\s*[:=]\s*["\'][^"\']+["\']'
Grep: 'BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY'

# SQL Injection
Grep: '(execute|query|raw)\s*\([^)]*\+|f["\'].*\{.*\}.*SELECT|INSERT|UPDATE|DELETE'

# Command Injection
Grep: '(exec|system|popen|subprocess|shell_exec|eval)\s*\('

# XSS
Grep: 'innerHTML\s*=|dangerouslySetInnerHTML|v-html='

# Path Traversal
Grep: '\.\./|\.\.\\'
Grep: '(readFile|open|include|require)\s*\([^)]*\+'
EOF
    ;;

  performance)
    cat << 'EOF'
# N+1 Queries
Grep: 'for.*in.*\.all\(\)|forEach.*await.*find|\.map\(.*=>.*await'

# Missing eager loading
Grep: '\.include\(|\.prefetch_related\(|\.select_related\('

# Nested loops (O(n²))
Grep: 'for.*for.*in|\.forEach.*\.forEach|\.map.*\.filter'

# Linear search in loop
Grep: 'for.*\.includes\(|for.*\.indexOf\(|for.*\.find\('

# Allocations in loops
Grep: 'for.*new |while.*new |\.map\(.*new '

# Memory leaks
Grep: 'addEventListener|setInterval|setTimeout|subscribe'
EOF
    ;;

  accessibility)
    cat << 'EOF'
# Missing alt text
Grep: '<img(?![^>]*alt=)[^>]*>'

# Missing form labels
Grep: '<input(?![^>]*aria-label)[^>]*(?!.*<label)'

# Click without keyboard
Grep: 'onClick(?![^}]*onKeyDown|onKeyPress|onKeyUp)'

# Non-semantic interactive
Grep: '<div[^>]*onClick(?![^>]*role=)'

# Removed focus outline
Grep: 'outline:\s*none|outline:\s*0[^.]'
EOF
    ;;

  deadcode)
    cat << 'EOF'
# Unreachable code patterns
Grep: 'return.*\n\s*[^}]|throw.*\n\s*[^}]'

# Commented out code blocks
Grep: '^\s*//.*function|^\s*#.*def '

# TODO/FIXME (potential dead)
Grep: 'TODO|FIXME|HACK|XXX'
EOF
    ;;

  *)
    echo "Usage: review-patterns.sh [security|performance|accessibility|deadcode]"
    ;;
esac
