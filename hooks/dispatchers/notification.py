#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Notification Dispatcher - Handle Claude Code notification events.

Delegates to handlers/notification.py for:
- permission_prompt: Permission dialog shown
- idle_prompt: Claude idle for 60+ seconds
- auth_success: Authentication succeeded
- elicitation_dialog: MCP tool needs input

Runs on Notification event for system notifications.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.notification import handle_notification


class NotificationDispatcher(SimpleDispatcher):
    """Notification event dispatcher."""

    DISPATCHER_NAME = "notification_handler"
    EVENT_TYPE = "Notification"

    def handle(self, ctx: dict) -> list[str]:
        return handle_notification(ctx)


if __name__ == "__main__":
    NotificationDispatcher().run()
