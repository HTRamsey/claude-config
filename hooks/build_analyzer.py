#!/usr/bin/env python3
"""
Build error analyzer - PostToolUse hook for Bash commands.

Detects build failures and provides structured error summaries with
suggestions for common issues.

Triggered: PostToolUse on Bash commands containing build-related keywords.
"""

import json
import re
import sys
from pathlib import Path

# Add hooks dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import graceful_main, output_message

# Build command patterns - pre-compiled for performance
_BUILD_PATTERNS_RAW = [
    r'\bmake\b', r'\bcmake\b', r'\bninja\b',
    r'\bcargo\s+(build|check|test|clippy)',
    r'\bnpm\s+(run\s+)?build', r'\byarn\s+build', r'\bpnpm\s+build',
    r'\bgo\s+(build|test|install)',
    r'\bpython.*setup\.py\s+build',
    r'\bpip\s+install',
    r'\bgcc\b', r'\bg\+\+\b', r'\bclang\b',
    r'\bgradlew?\s+build', r'\bmvn\s+(compile|package|install)',
    r'\brustc\b',
    r'\btsc\b',  # TypeScript compiler
    r'\bwebpack\b', r'\bvite\s+build', r'\besbuild\b',
]
BUILD_COMMANDS = [re.compile(p, re.IGNORECASE) for p in _BUILD_PATTERNS_RAW]

# Error patterns by build tool - pre-compiled for performance
_ERROR_PATTERNS_RAW = {
    'gcc_clang': [
        r'(\S+):(\d+):(\d+): error: (.+)',
        r'(\S+):(\d+): error: (.+)',
        r"undefined reference to `(.+)'",
        r'fatal error: (.+): No such file or directory',
    ],
    'rust': [
        r'error\[E(\d+)\]: (.+)',
        r'--> (\S+):(\d+):(\d+)',
        r"cannot find .+ `(.+)` in",
    ],
    'typescript': [
        r'(\S+)\((\d+),(\d+)\): error TS(\d+): (.+)',
        r"Property '(.+)' does not exist",
        r"Cannot find module '(.+)'",
    ],
    'python': [
        r'(\S+\.py):(\d+): (.+Error:.+)',
        r'ModuleNotFoundError: No module named \'(.+)\'',
        r'SyntaxError: (.+)',
    ],
    'go': [
        r'(\S+\.go):(\d+):(\d+): (.+)',
        r'undefined: (\S+)',
        r'cannot find package "(.+)"',
    ],
    'npm': [
        r'npm ERR! (.+)',
        r'Module not found: (.+)',
        r"Cannot find module '(.+)'",
    ],
    'make': [
        r'make.*: \*\*\* \[(.+)\] Error (\d+)',
        r'make.*: (.+): No such file or directory',
    ],
}
ERROR_PATTERNS = {
    tool: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tool, patterns in _ERROR_PATTERNS_RAW.items()
}

# Common fix suggestions
FIX_SUGGESTIONS = {
    'undefined reference': 'Missing library linkage. Check -l flags or add library to CMakeLists.txt/Makefile.',
    'No such file or directory': 'Missing header or file. Install dev package or check include paths.',
    'cannot find module': 'Missing dependency. Run npm install / pip install / cargo add.',
    'ModuleNotFoundError': 'Missing Python package. Run: pip install <package>',
    'Cannot find module': 'Missing npm package. Run: npm install <package>',
    'undefined:': 'Undefined symbol in Go. Check imports or variable declarations.',
    'error[E0432]': 'Rust: unresolved import. Check mod.rs or Cargo.toml dependencies.',
    'error[E0433]': 'Rust: failed to resolve. Add use statement or check crate name.',
    'TS2307': 'TypeScript: Cannot find module. Install @types package or check tsconfig paths.',
    'TS2339': 'TypeScript: Property does not exist. Check type definitions.',
    'implicit declaration': 'C: Missing function declaration. Add #include for the header.',
    'expected': 'Syntax error. Check for missing semicolons, braces, or parentheses.',
}


def is_build_command(command: str) -> bool:
    """Check if command is a build-related command."""
    for pattern in BUILD_COMMANDS:
        if pattern.search(command):
            return True
    return False


def detect_build_tool(command: str, output: str) -> str:
    """Detect which build tool was used."""
    cmd_lower = command.lower()

    if 'cargo' in cmd_lower or 'rustc' in cmd_lower:
        return 'rust'
    if 'npm' in cmd_lower or 'yarn' in cmd_lower or 'pnpm' in cmd_lower:
        return 'npm'
    if 'tsc' in cmd_lower or 'typescript' in output.lower():
        return 'typescript'
    if 'go ' in cmd_lower:
        return 'go'
    if 'python' in cmd_lower or 'pip' in cmd_lower:
        return 'python'
    if any(x in cmd_lower for x in ['gcc', 'g++', 'clang', 'make', 'cmake', 'ninja']):
        return 'gcc_clang'
    if 'gradle' in cmd_lower or 'mvn' in cmd_lower:
        return 'java'

    # Detect from output
    if 'error[E' in output:
        return 'rust'
    if 'error TS' in output:
        return 'typescript'
    if '.go:' in output and 'undefined' in output:
        return 'go'

    return 'make'  # Default fallback


def extract_errors(output: str, tool: str) -> list:
    """Extract error messages from build output."""
    errors = []
    patterns = ERROR_PATTERNS.get(tool, ERROR_PATTERNS['make'])

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        for pattern in patterns:
            match = pattern.search(line)
            if match:
                errors.append({
                    'line': line[:200],
                    'match': match.group(0)[:150],
                })
                break

        if len(errors) < 20 and 'error' in line.lower() and line not in [e['line'] for e in errors]:
            if not any(skip in line.lower() for skip in ['warning', 'note:', 'help:']):
                errors.append({'line': line[:200], 'match': None})

    return errors[:15]


def get_suggestions(errors: list, output: str) -> list:
    """Get fix suggestions based on errors."""
    suggestions = set()

    combined = output + ' '.join(e.get('match') or e.get('line', '') for e in errors)

    for pattern, suggestion in FIX_SUGGESTIONS.items():
        if pattern.lower() in combined.lower():
            suggestions.add(suggestion)

    return list(suggestions)[:5]


def count_errors_warnings(output: str) -> tuple:
    """Count errors and warnings in output."""
    error_count = len(re.findall(r'\berror[:\[]', output, re.IGNORECASE))
    warning_count = len(re.findall(r'\bwarning[:\[]', output, re.IGNORECASE))

    # Also check for "X errors" pattern
    match = re.search(r'(\d+)\s+error', output, re.IGNORECASE)
    if match:
        error_count = max(error_count, int(match.group(1)))

    return error_count, warning_count


def analyze_build(command: str, output: str, exit_code: int) -> dict | None:
    """Analyze build output and return summary."""

    # Only analyze failures
    if exit_code == 0:
        return None

    # Check if it's a build command
    if not is_build_command(command):
        return None

    tool = detect_build_tool(command, output)
    errors = extract_errors(output, tool)
    suggestions = get_suggestions(errors, output)
    error_count, warning_count = count_errors_warnings(output)

    # Only report if we found something useful
    if not errors and error_count == 0:
        return None

    return {
        'tool': tool,
        'exit_code': exit_code,
        'error_count': max(error_count, len(errors)),
        'warning_count': warning_count,
        'errors': errors[:5],  # First 5 for summary
        'suggestions': suggestions,
    }


def format_summary(analysis: dict) -> str:
    """Format analysis as readable summary."""
    lines = [
        f"\n## Build Analysis ({analysis['tool']})",
        f"**Status:** Failed (exit {analysis['exit_code']})",
        f"**Errors:** {analysis['error_count']} | **Warnings:** {analysis['warning_count']}",
        "",
    ]

    if analysis['errors']:
        lines.append("### First Errors:")
        for i, err in enumerate(analysis['errors'][:3], 1):
            lines.append(f"{i}. `{err['line'][:100]}`")
        lines.append("")

    if analysis['suggestions']:
        lines.append("### Suggestions:")
        for sug in analysis['suggestions']:
            lines.append(f"- {sug}")
        lines.append("")

    return '\n'.join(lines)


def analyze_build_post(ctx: dict) -> dict | None:
    """Handler function for dispatcher integration."""
    # Only process Bash
    if ctx.get('tool_name') != 'Bash':
        return None

    tool_input = ctx.get('tool_input', {})
    # Claude Code uses "tool_response" for PostToolUse hooks
    tool_result = ctx.get('tool_response') or ctx.get('tool_result', {})

    command = tool_input.get('command', '')
    output = str(tool_result.get('stdout', '')) + str(tool_result.get('stderr', ''))

    # Get exit code - check multiple possible locations
    exit_code = tool_result.get('exit_code')
    if exit_code is None:
        exit_code = tool_result.get('exitCode')
    if exit_code is None:
        # Try to detect from output
        if 'error' in output.lower() and ('make: ***' in output or 'FAILED' in output):
            exit_code = 1
        else:
            exit_code = 0

    if exit_code == 0:
        return None

    analysis = analyze_build(command, output, exit_code)

    if analysis:
        summary = format_summary(analysis)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": summary
            }
        }

    return None


@graceful_main("build_analyzer")
def main():
    """Standalone execution for testing."""
    ctx = json.load(sys.stdin)
    result = analyze_build_post(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        if msg:
            output_message(msg)


if __name__ == "__main__":
    main()
