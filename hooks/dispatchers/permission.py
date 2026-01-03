#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PermissionRequest Dispatcher - Handle permission request events.

Delegates to handlers/smart_permissions.py for:
- Static patterns: Known-safe file types (test files, docs, configs)
- Learned patterns: User consistently approves → auto-approve

Runs on PermissionRequest event to auto-approve known-safe operations.

Note: Uses JSON output format (not SimpleDispatcher's string format)
because PermissionRequest requires hookSpecificOutput response.
"""
import json
import sys

from hooks.hook_utils import graceful_main, log_event
from hooks.config import fast_json_loads
from hooks.handlers.smart_permissions import handle_permission_request


@graceful_main("permission_dispatcher")
def main():
    try:
        raw = fast_json_loads(sys.stdin.read())
    except Exception as e:
        log_event("permission_dispatcher", "parse_error", {"error": str(e)})
        sys.exit(1)

    result = handle_permission_request(raw)

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
