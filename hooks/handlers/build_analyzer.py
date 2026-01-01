#!/usr/bin/env python3
"""
Build error analyzer - PostToolUse hook for Bash commands.

Detects build failures and provides structured error summaries with
suggestions for common issues.

Triggered: PostToolUse on Bash commands containing build-related keywords.
"""

import re
from pathlib import Path

# Add hooks dir to path for imports
from hooks.hook_sdk import PostToolUseContext, Response, run_standalone
from hooks.config import Build

# Import patterns from centralized config
BUILD_COMMANDS = Build.get_build_commands()
ERROR_PATTERNS = Build.get_error_patterns()
FIX_SUGGESTIONS = Build.FIX_SUGGESTIONS


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

        for pattern, category in patterns:
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


def _check_build_success(exit_code: int, command: str) -> dict | None:
    """Check if build failed and is a valid build command."""
    if exit_code == 0:
        return None
    if not is_build_command(command):
        return None
    return {}  # Placeholder - indicates success


def _analyze_errors(command: str, output: str) -> dict:
    """Extract errors, suggestions, and counts from build output."""
    tool = detect_build_tool(command, output)
    errors = extract_errors(output, tool)
    suggestions = get_suggestions(errors, output)
    error_count, warning_count = count_errors_warnings(output)

    return {
        'tool': tool,
        'errors': errors,
        'suggestions': suggestions,
        'error_count': error_count,
        'warning_count': warning_count,
    }


def analyze_build(command: str, output: str, exit_code: int) -> dict | None:
    """Analyze build output and return summary."""
    # Check validity
    if not _check_build_success(exit_code, command):
        return None

    # Analyze errors and counts
    analysis = _analyze_errors(command, output)

    # Only report if we found something useful
    if not analysis['errors'] and analysis['error_count'] == 0:
        return None

    return {
        'tool': analysis['tool'],
        'exit_code': exit_code,
        'error_count': max(analysis['error_count'], len(analysis['errors'])),
        'warning_count': analysis['warning_count'],
        'errors': analysis['errors'][:5],
        'suggestions': analysis['suggestions'],
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


def analyze_build_post(raw: dict) -> dict | None:
    """Handler function for dispatcher integration."""
    ctx = PostToolUseContext(raw)

    # Only process Bash
    if ctx.tool_name != 'Bash':
        return None

    command = ctx.tool_input.command
    output = ctx.tool_result.output

    # Get exit code
    exit_code = ctx.tool_result.exit_code
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
        return Response.message(summary, event="PostToolUse")

    return None


if __name__ == "__main__":
    run_standalone(analyze_build_post)
