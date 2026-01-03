"""
Tool failure handler - Track and analyze tool execution failures.

Extracts tool-specific details from failures for analytics and debugging.

Used by dispatchers/post_tool_failure.py
"""
from hooks.hook_utils import log_event


def handle_tool_failure(ctx: dict) -> list[str]:
    """Handle PostToolUseFailure event.

    Args:
        ctx: Context with tool_name, tool_input, error, exit_code (for Bash)

    Returns:
        List of messages (usually empty - logging only)
    """
    tool_name = ctx.get("tool_name", "unknown")
    error = ctx.get("error", "")
    tool_input = ctx.get("tool_input", {})

    details = extract_failure_details(tool_name, tool_input, error, ctx)
    log_event("tool_failure", tool_name, details)

    # No user-facing messages by default
    # The tool failure is already visible to the user
    return []


def extract_failure_details(tool_name: str, tool_input: dict, error: str, ctx: dict) -> dict:
    """Extract tool-specific details from a failure.

    Args:
        tool_name: Name of the failed tool
        tool_input: Tool input parameters
        error: Error message
        ctx: Full context dict

    Returns:
        Dict of relevant details for logging
    """
    details = {"tool": tool_name, "error": error[:200]}

    extractors = {
        "Bash": _extract_bash_details,
        "Read": _extract_file_details,
        "Edit": _extract_edit_details,
        "Write": _extract_file_details,
        "Task": _extract_task_details,
        "Grep": _extract_pattern_details,
        "Glob": _extract_pattern_details,
    }

    extractor = extractors.get(tool_name)
    if extractor:
        extractor(details, tool_input, ctx)

    return details


def _extract_bash_details(details: dict, tool_input: dict, ctx: dict) -> None:
    """Extract Bash-specific failure details."""
    details["command"] = (tool_input.get("command") or "")[:100]
    details["exit_code"] = ctx.get("exit_code")


def _extract_file_details(details: dict, tool_input: dict, ctx: dict) -> None:
    """Extract file operation failure details."""
    details["file_path"] = tool_input.get("file_path", "")


def _extract_edit_details(details: dict, tool_input: dict, ctx: dict) -> None:
    """Extract Edit-specific failure details."""
    details["file_path"] = tool_input.get("file_path", "")
    details["old_string_len"] = len(tool_input.get("old_string", ""))


def _extract_task_details(details: dict, tool_input: dict, ctx: dict) -> None:
    """Extract Task-specific failure details."""
    details["subagent_type"] = tool_input.get("subagent_type", "")


def _extract_pattern_details(details: dict, tool_input: dict, ctx: dict) -> None:
    """Extract Grep/Glob failure details."""
    details["pattern"] = tool_input.get("pattern", "")
