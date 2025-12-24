#!/home/jonglaser/.claude/venv/bin/python3
"""
Tool Optimization Hook - Suggests better tool alternatives.
Runs on PreToolUse to recommend token-saving alternatives.

Returns suggestions as messages (does not block execution).
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

# Patterns that suggest subagent would be better
EXPLORATION_PATTERNS = [
    r"where.*implemented",
    r"how.*work",
    r"find.*all",
    r"search.*for",
    r"look.*for",
]

# Bash commands that have better alternatives
BASH_ALTERNATIVES = {
    # Search tools
    r"^grep\s": ("offload-grep.sh", "97% token savings"),
    r"^rg\s": ("offload-grep.sh", "97% token savings"),
    r"^find\s": ("offload-find.sh", "95% token savings"),
    # Git tools
    r"^git\s+diff": ("smart-diff.sh", "uses delta, 99% savings on large diffs"),
    r"^git\s+log.*-p": ("smart-diff.sh", "pipe through smart-diff"),
    # Build/test output
    r"^cat\s.*\.(log|txt)": ("compress-logs.sh", "errors/warnings only"),
    r"^npm\s+(test|run\s+test)": ("compress-tests.sh", "pipe output"),
    r"^pytest": ("compress-tests.sh", "pipe output"),
    r"^make\b": ("compress-build.sh", "pipe for errors only"),
    r"^cmake\b": ("compress-build.sh", "pipe for errors only"),
    # Directory listing - use eza for 87% smaller output
    r"^ls\s+(-la|-l|-a)": ("smart-ls.sh", "uses eza, 87% smaller output"),
    r"^ls\s*$": ("smart-ls.sh", "uses eza, 87% smaller output"),
    # Tree view
    r"^tree\s": ("smart-tree.sh", "uses eza --tree, respects .gitignore"),
    # Sed replacements - sd is simpler
    r"^sed\s": ("smart-replace.sh", "uses sd, simpler syntax"),
    # fd - faster find with .gitignore support
    r"^find\s.*-name": ("smart-find.sh", "uses fd, 10x faster, respects .gitignore"),
    # bat - syntax highlighted cat
    r"^cat\s": ("smart-cat.sh", "uses bat, syntax highlighting + line numbers"),
    r"^head\s": ("smart-cat.sh", "uses bat with line range"),
    r"^tail\s": ("smart-cat.sh", "uses bat with line range"),
    # dust - better disk usage
    r"^du\s": ("smart-du.sh", "uses dust, compact visual output"),
    # difftastic - structural diff
    r"^diff\s": ("smart-difft.sh", "uses difftastic, structural diff"),
    # git blame - skip noise commits
    r"^git\s+blame": ("smart-blame.sh", "filters formatting commits, adds context"),
    # jq - suggest smart-json for simpler syntax
    r"^(cat|less).*\.json\s*\|\s*jq": ("smart-json.sh", "simpler field extraction syntax"),
    # ast-grep - structural code search
    r"^grep.*def\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*class\s": ("smart-ast.sh", "uses ast-grep, finds class definitions structurally"),
    r"^grep.*function\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*import\s": ("smart-ast.sh", "uses ast-grep, finds imports structurally"),
}

# Read patterns suggesting exploration
READ_EXPLORATION_THRESHOLD = 3  # If reading 3+ files, suggest Task(Explore)

def check_bash_alternatives(command: str) -> str | None:
    """Check if bash command has a better alternative."""
    cmd_lower = command.strip().lower()

    for pattern, (alt, reason) in BASH_ALTERNATIVES.items():
        if re.search(pattern, command.strip(), re.IGNORECASE):
            return f"Consider ~/.claude/scripts/{alt} ({reason})"

    return None

def check_grep_optimization(tool_input: dict) -> str | None:
    """Check if Grep usage could be optimized."""
    pattern = tool_input.get("pattern", "")
    output_mode = tool_input.get("output_mode", "files_with_matches")

    # If content mode without head_limit, suggest limiting
    if output_mode == "content" and not tool_input.get("head_limit"):
        return "Add head_limit to Grep to reduce token usage"

    return None

def check_read_optimization(tool_input: dict, session_reads: int) -> str | None:
    """Check if Read usage suggests exploration."""
    file_path = tool_input.get("file_path", "")

    # Large file warning
    try:
        if file_path and Path(file_path).exists():
            size = Path(file_path).stat().st_size
            if size > 50000:  # 50KB
                return "Large file - consider smart-preview.sh or summarize-file.sh"
    except Exception:
        pass

    # Multiple reads suggest exploration
    if session_reads >= READ_EXPLORATION_THRESHOLD:
        return "Multiple file reads - consider Task(subagent_type=Explore) for exploration"

    return None

def suggest_optimization(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    suggestion = None

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        suggestion = check_bash_alternatives(command)

    elif tool_name == "Grep":
        suggestion = check_grep_optimization(tool_input)

    elif tool_name == "Read":
        # Track reads in session (simplified - just check this call)
        suggestion = check_read_optimization(tool_input, session_reads=1)

    if suggestion:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Optimization] {suggestion}"
            }
        }

    return None


@graceful_main("suggest_tool_optimization")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = suggest_optimization(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
