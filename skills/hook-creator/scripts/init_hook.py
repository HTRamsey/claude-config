#!/usr/bin/env python3
"""
Hook Initializer - Creates a new hook from template

Usage:
    init_hook.py <hook-name> --event <event> --watches <tools> [--description "<description>"]

Examples:
    init_hook.py my-hook --event PreToolUse --watches Read,Write --description "Block specific files"
    init_hook.py build-monitor --event PostToolUse --watches Bash --description "Track build failures"
"""

import sys
from pathlib import Path

# Event-specific templates
PRETOOLUSE_TEMPLATE = '''#!/home/jonglaser/.claude/venv/bin/python3
"""
{description}

PreToolUse hook for {watches} tools.
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event


def {handler_name}(ctx: dict) -> dict | None:
    """
    Handler function for {hook_name}.

    Args:
        ctx: Context dict containing:
            - tool_name: Name of the tool being invoked
            - tool_input: Input parameters for the tool

    Returns:
        dict with hookSpecificOutput, or None to allow operation

    Example return to block:
        return {{
            "hookSpecificOutput": {{
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Reason for blocking"
            }}
        }}

    Example return to allow with warning:
        return {{
            "hookSpecificOutput": {{
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "[WARNING] Some message"
            }}
        }}
    """
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {{}})

    # TODO: Implement your logic here
    # Example: Check if tool is in watched list
    watched_tools = {watched_tools_list}
    if tool_name not in watched_tools:
        return None

    # TODO: Add your check logic
    # Example decision logic:
    # if some_condition:
    #     log_event("{hook_name}", "blocked", {{"reason": "some reason"}})
    #     return {{
    #         "hookSpecificOutput": {{
    #             "hookEventName": "PreToolUse",
    #             "permissionDecision": "deny",
    #             "permissionDecisionReason": "Blocked: some reason"
    #         }}
    #     }}

    return None


@graceful_main("{hook_name}")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = {handler_name}(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
'''

POSTTOOLUSE_TEMPLATE = '''#!/home/jonglaser/.claude/venv/bin/python3
"""
{description}

PostToolUse hook for {watches} tools.
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event


def {handler_name}(ctx: dict) -> dict | None:
    """
    Handler function for {hook_name}.

    Args:
        ctx: Context dict containing:
            - tool_name: Name of the tool that was invoked
            - tool_input: Input parameters for the tool
            - tool_result: Result from the tool execution
            - duration_ms: Time taken for the tool to execute

    Returns:
        dict with message to display, or None

    Example return to display message:
        return {{
            "hookSpecificOutput": {{
                "message": "Some informational message"
            }}
        }}
    """
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {{}})
    tool_result = ctx.get("tool_result", {{}})
    duration_ms = ctx.get("duration_ms", 0)

    # TODO: Implement your logic here
    # Example: Check if tool is in watched list
    watched_tools = {watched_tools_list}
    if tool_name not in watched_tools:
        return None

    # TODO: Add your processing logic
    # Example: Log event
    # log_event("{hook_name}", "processed", {{
    #     "tool": tool_name,
    #     "duration": duration_ms
    # }})

    # Example: Return message to display
    # return {{
    #     "hookSpecificOutput": {{
    #         "message": f"Tool {{tool_name}} completed in {{duration_ms}}ms"
    #     }}
    # }}

    return None


@graceful_main("{hook_name}")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = {handler_name}(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
'''

OTHER_EVENT_TEMPLATE = '''#!/home/jonglaser/.claude/venv/bin/python3
"""
{description}

{event_type} hook.
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event, read_stdin_context


def {handler_name}(ctx: dict) -> dict | None:
    """
    Handler function for {hook_name}.

    Args:
        ctx: Context dict (varies by event type)

    Returns:
        dict with hookSpecificOutput, or None
    """
    # TODO: Implement your logic here
    # Example: Log the event
    # log_event("{hook_name}", "triggered", {{"event": "{event_type}"}})

    return None


@graceful_main("{hook_name}")
def main():
    ctx = read_stdin_context()
    result = {handler_name}(ctx)

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
'''


def snake_to_handler_name(hook_name: str) -> str:
    """Convert hook-name to handler_name."""
    return hook_name.replace('-', '_')


def init_hook(hook_name, event_type, watches, description):
    """
    Initialize a new hook Python file.

    Args:
        hook_name: Name of the hook (kebab-case)
        event_type: Hook event type (PreToolUse, PostToolUse, etc.)
        watches: Comma-separated list of tools to watch
        description: Hook description

    Returns:
        Path to created hook file, or None if error
    """
    hooks_dir = Path.home() / '.claude' / 'hooks'

    # Ensure hooks directory exists
    if not hooks_dir.exists():
        print(f"❌ Error: Hooks directory does not exist: {hooks_dir}")
        return None

    hook_file = hooks_dir / f"{hook_name}.py"

    # Check if file already exists
    if hook_file.exists():
        print(f"❌ Error: Hook already exists: {hook_file}")
        return None

    # Validate event type
    valid_events = [
        'PreToolUse', 'PostToolUse', 'SessionStart', 'SessionEnd',
        'UserPromptSubmit', 'PreCompact', 'SubagentStart', 'SubagentStop',
        'PermissionRequest'
    ]
    if event_type not in valid_events:
        print(f"❌ Error: Invalid event type '{event_type}'")
        print(f"Valid events: {', '.join(valid_events)}")
        return None

    # Parse watches
    watched_tools = [t.strip() for t in watches.split(',')]
    watched_tools_list = repr(watched_tools)

    # Generate handler function name
    handler_name = snake_to_handler_name(hook_name)

    # Select template based on event type
    if event_type == 'PreToolUse':
        template = PRETOOLUSE_TEMPLATE
    elif event_type == 'PostToolUse':
        template = POSTTOOLUSE_TEMPLATE
    else:
        template = OTHER_EVENT_TEMPLATE

    # Create hook content
    content = template.format(
        hook_name=hook_name,
        handler_name=handler_name,
        description=description,
        event_type=event_type,
        watches=watches,
        watched_tools_list=watched_tools_list
    )

    try:
        hook_file.write_text(content)
        # Make executable
        hook_file.chmod(0o755)
        print(f"✅ Created hook: {hook_file}")
    except Exception as e:
        print(f"❌ Error creating hook: {e}")
        return None

    print(f"\n✅ Hook '{hook_name}' initialized successfully")
    print(f"   Event: {event_type}")
    print(f"   Watches: {watches}")
    print("\nNext steps:")
    print("1. Edit the hook file to implement TODO sections")
    print("2. Update the handler function with your logic")
    print("3. Test the hook with ~/.claude/scripts/diagnostics/test-hooks.sh")
    print("4. Register the hook in settings.json hooks section if needed")

    return hook_file


def main():
    args = sys.argv[1:]

    if len(args) < 5 or '--event' not in args or '--watches' not in args:
        print("Usage: init_hook.py <hook-name> --event <event> --watches <tools> [--description \"<description>\"]")
        print("\nArguments:")
        print("  hook-name     : Kebab-case identifier (e.g., 'my-hook')")
        print("  --event       : Hook event type")
        print("  --watches     : Comma-separated tools to watch (e.g., 'Read,Write,Edit')")
        print("  --description : Hook description (optional)")
        print("\nValid event types:")
        print("  PreToolUse       - Before tool execution (can block)")
        print("  PostToolUse      - After tool execution (observe/react)")
        print("  SessionStart     - When session begins")
        print("  SessionEnd       - When session ends")
        print("  UserPromptSubmit - When user submits a prompt")
        print("  PreCompact       - Before context compaction")
        print("  SubagentStart    - When subagent starts")
        print("  SubagentStop     - When subagent stops")
        print("  PermissionRequest- When permission is requested")
        print("\nExamples:")
        print("  init_hook.py file-validator --event PreToolUse --watches Read,Write")
        print("  init_hook.py build-monitor --event PostToolUse --watches Bash --description \"Track build failures\"")
        sys.exit(1)

    hook_name = args[0]

    # Parse --event
    try:
        event_idx = args.index('--event')
        event_type = args[event_idx + 1]
    except (ValueError, IndexError):
        print("❌ Error: --event is required")
        sys.exit(1)

    # Parse --watches
    try:
        watches_idx = args.index('--watches')
        watches = args[watches_idx + 1]
    except (ValueError, IndexError):
        print("❌ Error: --watches is required")
        sys.exit(1)

    # Parse --description (optional)
    description = f"{hook_name} hook"
    if '--description' in args:
        try:
            desc_idx = args.index('--description')
            description = args[desc_idx + 1]
        except IndexError:
            pass

    print(f"🚀 Initializing hook: {hook_name}")
    print(f"   Event: {event_type}")
    print(f"   Watches: {watches}")
    print()

    result = init_hook(hook_name, event_type, watches, description)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
