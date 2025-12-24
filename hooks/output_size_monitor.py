#!/home/jonglaser/.claude/venv/bin/python3
"""Monitor tool output sizes and warn about excessive output.

PostToolUse hook that tracks output sizes and warns when they're too large.
Helps prevent context bloat from verbose tool responses.
"""
import json
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


# Configuration
OUTPUT_WARNING_THRESHOLD = 10000  # Warn if output > 10K chars
OUTPUT_CRITICAL_THRESHOLD = 50000  # Strong warning if > 50K chars
CHARS_PER_TOKEN = 4

# Tools with expected large output (don't warn as aggressively)
LARGE_OUTPUT_TOOLS = ["Task", "WebFetch", "WebSearch"]

def estimate_tokens(char_count: int) -> int:
    """Estimate tokens from character count"""
    return char_count // CHARS_PER_TOKEN

def get_output_size(tool_response) -> int:
    """Get size of tool response in characters"""
    if isinstance(tool_response, str):
        return len(tool_response)
    elif isinstance(tool_response, dict):
        return len(json.dumps(tool_response))
    elif isinstance(tool_response, list):
        return sum(get_output_size(item) for item in tool_response)
    return 0

@graceful_main("output_size_monitor")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_result = ctx.get("tool_result", {})

    output_size = get_output_size(tool_result)

    if output_size == 0:
        sys.exit(0)

    estimated_tokens = estimate_tokens(output_size)

    # Adjust thresholds for tools expected to have large output
    warning_threshold = OUTPUT_WARNING_THRESHOLD
    critical_threshold = OUTPUT_CRITICAL_THRESHOLD
    if tool_name in LARGE_OUTPUT_TOOLS:
        warning_threshold *= 3
        critical_threshold *= 3

    if output_size >= critical_threshold:
        print(f"[Output Monitor] Large output from {tool_name}: ~{estimated_tokens:,} tokens ({output_size:,} chars)")
        print("  Consider using compression scripts or limiting output.")
        if tool_name == "Bash":
            print("  Tip: Pipe to head, use compress-*.sh scripts, or add output limits")
        elif tool_name == "Grep":
            print("  Tip: Use head_limit parameter or offload-grep.sh")
        elif tool_name == "Read":
            print("  Tip: Use smart-preview.sh or summarize-file.sh for large files")

    elif output_size >= warning_threshold:
        print(f"[Output Monitor] {tool_name} output: ~{estimated_tokens:,} tokens")

    sys.exit(0)

if __name__ == "__main__":
    main()
