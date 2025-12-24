#!/home/jonglaser/.claude/venv/bin/python3
"""Block dangerous bash commands that could cause system damage.

PreToolUse hook for Bash tool.
Blocks or warns about commands that could cause irreversible damage.
"""
import json
import re
import sys
from pathlib import Path

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

# Commands that are BLOCKED (exit 2)
BLOCKED_PATTERNS = [
    # Destructive file operations
    (r'\brm\s+(-[rf]+\s+)*(/|/\*|/home|/etc|/usr|/var|/boot|~|\$HOME)(\s|$)', "rm on system directory"),
    (r'\brm\s+-[rf]*\s*\*\s*$', "rm with bare wildcard"),
    (r'>\s*/dev/sd[a-z]', "write to block device"),
    (r'\bdd\s+.*of=/dev/sd[a-z]', "dd to block device"),
    (r'\bmkfs\b', "filesystem format"),
    (r'\bfdisk\b', "disk partitioning"),

    # System destruction
    (r':\(\)\{\s*:\|:&\s*\};\s*:', "fork bomb"),
    (r'\bchmod\s+-R\s+777\s+/', "chmod 777 on root"),
    (r'\bchown\s+-R\s+.*\s+/', "chown on root"),

    # Network attacks
    (r'\b(nc|netcat)\s+.*-e\s*/bin/(ba)?sh', "reverse shell"),

    # Credential theft / remote code execution
    (r'curl\s+.*\|\s*(ba)?sh', "curl pipe to shell"),
    (r'wget\s+.*-O\s*-\s*\|\s*(ba)?sh', "wget pipe to shell"),
    # Expanded patterns to catch bypasses
    (r'(curl|wget)\s+[^|]*\|\s*(python|ruby|perl|node|php)', "download pipe to interpreter"),
    (r'(curl|wget)\s+-[qsS]*o?\s*-[^|]*\|\s*\w*sh', "download pipe to shell (alternate syntax)"),
    (r'(curl|wget)[^;|&]*[;|&]\s*(ba)?sh\s', "download then execute"),
    (r'\beval\s+\$', "eval with variable expansion"),
    (r'\bsource\s+<\(', "source from process substitution"),
    (r'\bbase64\s+-d.*\|\s*(ba)?sh', "base64 decode to shell"),

    # Additional dangerous patterns
    (r'\bxargs\s+.*\brm\b', "xargs with rm"),
    (r'\bfind\s+.*-exec\s+.*rm', "find with rm exec"),
    (r'>\s*/etc/', "redirect to /etc"),
    (r'\bsudo\s+rm\s+-rf\s+/', "sudo rm -rf /"),
    (r'\bhistory\s+-c', "clear shell history"),
    (r'unset\s+HISTFILE', "disable history"),
    (r'\biptables\s+-F', "flush iptables"),
    (r'\bsystemctl\s+(stop|disable)\s+(ssh|sshd|firewall)', "disable security services"),
]

# Commands that get WARNINGS (exit 0 with message)
WARNING_PATTERNS = [
    (r'\brm\s+-[rf]', "recursive/force remove"),
    (r'\bgit\s+push\s+.*--force', "force push"),
    (r'\bgit\s+reset\s+--hard', "hard reset"),
    (r'\bgit\s+clean\s+-[fd]', "git clean"),
    (r'\bsudo\s+', "sudo usage"),
    (r'\bchmod\s+777\b', "chmod 777"),
    (r'\bkill\s+-9\b', "kill -9"),
    (r'\bkillall\b', "killall"),
    (r'\bpkill\b', "pkill"),
    (r'>\s*/dev/null\s+2>&1', "silencing all output"),
    (r'\btruncate\b', "file truncation"),
    (r'\bshred\b', "secure delete"),
]

# Pre-compile patterns for performance (avoids recompilation each invocation)
BLOCKED_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in BLOCKED_PATTERNS]
WARNING_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in WARNING_PATTERNS]

def check_command(command: str) -> tuple:
    """
    Check command for dangerous patterns.
    Returns: (action, reason) where action is 'block', 'warn', or 'allow'
    """
    # Normalize command
    cmd = command.strip()

    # Check blocked patterns (using pre-compiled regexes)
    for compiled, reason in BLOCKED_COMPILED:
        if compiled.search(cmd):
            return ('block', reason)

    # Check warning patterns (using pre-compiled regexes)
    for compiled, reason in WARNING_COMPILED:
        if compiled.search(cmd):
            return ('warn', reason)

    return ('allow', None)

def check_dangerous_command(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_input = ctx.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        return None

    action, reason = check_command(command)

    if action == 'block':
        log_event("dangerous_command_blocker", "blocked", {"reason": reason, "command": command[:100]})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"[Dangerous Command] BLOCKED: {reason}. Command: {command[:100]}... This command could cause irreversible system damage."
            }
        }

    elif action == 'warn':
        log_event("dangerous_command_blocker", "warning", {"reason": reason, "command": command[:80]})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Dangerous Command] Warning: {reason}. Command: {command[:80]}..."
            }
        }

    return None


@graceful_main("dangerous_command_blocker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = check_dangerous_command(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
