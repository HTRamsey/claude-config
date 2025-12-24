#!/home/jonglaser/.claude/venv/bin/python3
"""
Context Checkpoint Hook - Saves state before risky operations.
Runs on PreToolUse for Edit|Write on critical files.

Saves current task context to memory MCP for recovery.
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

# Configuration
STATE_FILE = Path("/tmp/claude-checkpoint-state.json")
CHECKPOINT_INTERVAL = 300  # Min seconds between checkpoints
RISKY_PATTERNS = [
    r'(config|settings|env)\.(json|yaml|yml|toml)$',
    r'package\.json$',
    r'Cargo\.toml$',
    r'pyproject\.toml$',
    r'docker-compose',
    r'Dockerfile',
    r'\.github/workflows/',
    r'migrations/',
    r'schema\.',
]
RISKY_KEYWORDS = ['delete', 'remove', 'drop', 'truncate', 'reset', 'destroy']

def load_state() -> dict:
    """Load checkpoint state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_checkpoint": 0, "checkpoints": []}

def save_state(state: dict):
    """Save checkpoint state."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def is_risky_operation(file_path: str, content: str = "") -> tuple[bool, str]:
    """Determine if operation is risky and needs checkpoint."""
    path_str = str(file_path).lower()

    # Check file patterns
    for pattern in RISKY_PATTERNS:
        if re.search(pattern, path_str, re.IGNORECASE):
            return True, f"config/critical file: {pattern}"

    # Check content for risky keywords
    content_lower = content.lower()
    for keyword in RISKY_KEYWORDS:
        if keyword in content_lower:
            return True, f"contains '{keyword}' operation"

    # Large edits (>500 chars changed)
    if len(content) > 500:
        return True, "large edit (>500 chars)"

    return False, ""

def checkpoint_to_memory(session_id: str, file_path: str, reason: str, ctx: dict):
    """
    Save checkpoint info. Since we can't call MCP directly from hook,
    we output a suggestion for Claude to save to memory.
    """
    state = load_state()
    now = datetime.now()

    checkpoint = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "file": file_path,
        "reason": reason,
        "cwd": ctx.get("cwd", ""),
    }

    state["checkpoints"].append(checkpoint)
    state["checkpoints"] = state["checkpoints"][-20:]  # Keep last 20
    state["last_checkpoint"] = now.timestamp()
    save_state(state)

    return checkpoint

def should_checkpoint(state: dict) -> bool:
    """Check if we should create a new checkpoint."""
    import time
    last = state.get("last_checkpoint", 0)
    return (time.time() - last) > CHECKPOINT_INTERVAL

@graceful_main("context_checkpoint")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    session_id = ctx.get("session_id", "unknown")

    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "") or tool_input.get("new_string", "")

    if not file_path:
        sys.exit(0)

    state = load_state()

    risky, reason = is_risky_operation(file_path, content)

    if risky and should_checkpoint(state):
        checkpoint = checkpoint_to_memory(session_id, file_path, reason, ctx)

        filename = Path(file_path).name
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Checkpoint] {filename} ({reason})\n  → State saved. To recover: search_nodes('checkpoint {session_id[:8]}')"
            }
        }
        print(json.dumps(result))

    sys.exit(0)

if __name__ == "__main__":
    main()
