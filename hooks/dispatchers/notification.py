#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Notification Dispatcher - Handle Claude Code notification events.

Notification types:
- permission_prompt: Permission dialog shown
- idle_prompt: Claude idle for 60+ seconds
- auth_success: Authentication succeeded
- elicitation_dialog: MCP tool needs input

Runs on Notification event for system notifications.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.hook_utils import log_event, send_notification, is_notification_available


def handle_notification(ctx: dict) -> list[str]:
    """Handle Notification event.

    Args:
        ctx: Context with notification_type and type-specific fields

    Returns:
        List of messages (usually empty)
    """
    notification_type = ctx.get("notification_type", "unknown")

    log_event("notification", "received", {
        "notification_type": notification_type,
    })

    # Handle specific notification types
    if notification_type == "permission_prompt":
        return handle_permission_prompt(ctx)
    elif notification_type == "idle_prompt":
        return handle_idle_prompt(ctx)
    elif notification_type == "auth_success":
        return handle_auth_success(ctx)
    elif notification_type == "elicitation_dialog":
        return handle_elicitation(ctx)

    return []


def handle_permission_prompt(ctx: dict) -> list[str]:
    """Handle permission prompt notification."""
    tool_name = ctx.get("tool_name", "")
    log_event("notification", "permission_prompt", {"tool": tool_name})
    return []


def handle_idle_prompt(ctx: dict) -> list[str]:
    """Handle idle prompt notification - Claude waiting for input."""
    idle_seconds = ctx.get("idle_seconds", 60)

    # Send desktop notification if available and idle for significant time
    if idle_seconds >= 60 and is_notification_available():
        send_notification(
            "Claude is waiting",
            f"Idle for {idle_seconds}s - awaiting your input",
            urgency="low"
        )

    log_event("notification", "idle_prompt", {"idle_seconds": idle_seconds})
    return []


def handle_auth_success(ctx: dict) -> list[str]:
    """Handle authentication success notification."""
    log_event("notification", "auth_success", {})
    return []


def handle_elicitation(ctx: dict) -> list[str]:
    """Handle MCP elicitation dialog notification."""
    mcp_server = ctx.get("mcp_server", "")
    log_event("notification", "elicitation_dialog", {"mcp_server": mcp_server})
    return []


class NotificationDispatcher(SimpleDispatcher):
    """Notification event dispatcher."""

    DISPATCHER_NAME = "notification_handler"
    EVENT_TYPE = "Notification"

    def handle(self, ctx: dict) -> list[str]:
        return handle_notification(ctx)


if __name__ == "__main__":
    NotificationDispatcher().run()
