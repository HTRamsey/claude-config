"""
Tool Optimizer - Suggests better tool alternatives.

PreToolUse: Bash, Grep, Read
"""
import re
from pathlib import Path

from hook_sdk import PreToolUseContext, Response


# Pre-compiled patterns for performance
_BASH_ALTERNATIVES_RAW = {
    r"^grep\s": ("offload-grep.sh", "97% token savings"),
    r"^rg\s": ("offload-grep.sh", "97% token savings"),
    r"^find\s": ("offload-find.sh", "95% token savings"),
    r"^git\s+diff": ("smart-diff.sh", "uses delta, 99% savings on large diffs"),
    r"^cat\s.*\.(log|txt)": ("compress-logs.sh", "errors/warnings only"),
    r"^npm\s+(test|run\s+test)": ("compress.sh --type tests", "pipe output"),
    r"^pytest": ("compress.sh --type tests", "pipe output"),
    r"^make\b": ("compress.sh --type build", "pipe for errors only"),
    r"^cmake\b": ("compress.sh --type build", "pipe for errors only"),
    r"^ls\s+(-la|-l|-a)": ("smart-ls.sh", "uses eza, 87% smaller output"),
    r"^ls\s*$": ("smart-ls.sh", "uses eza, 87% smaller output"),
    r"^tree\s": ("smart-tree.sh", "uses eza --tree, respects .gitignore"),
    r"^sed\s": ("smart-replace.sh", "uses sd, simpler syntax"),
    r"^find\s.*-name": ("smart-find.sh", "uses fd, 10x faster, respects .gitignore"),
    r"^cat\s": ("smart/smart-view.sh", "unified viewer with syntax highlighting"),
    r"^head\s": ("smart/smart-view.sh", "unified viewer with line range"),
    r"^tail\s": ("smart/smart-view.sh", "unified viewer with line range"),
    r"^du\s": ("smart-du.sh", "uses dust, compact visual output"),
    r"^diff\s": ("smart-difft.sh", "uses difftastic, structural diff"),
    r"^git\s+blame": ("smart-blame.sh", "filters formatting commits, adds context"),
    r"^(cat|less).*\.json\s*\|\s*jq": ("smart-json.sh", "simpler field extraction syntax"),
    r"^grep.*def\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*class\s": ("smart-ast.sh", "uses ast-grep, finds class definitions structurally"),
    r"^grep.*function\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*import\s": ("smart-ast.sh", "uses ast-grep, finds imports structurally"),
}

BASH_ALTERNATIVES = [
    (re.compile(p, re.IGNORECASE), alt, reason)
    for p, (alt, reason) in _BASH_ALTERNATIVES_RAW.items()
]


def suggest_optimization(raw: dict) -> dict | None:
    """Suggest better tool alternatives."""
    ctx = PreToolUseContext(raw)

    suggestion = None

    if ctx.tool_name == "Bash":
        command = (ctx.tool_input.command or "").strip()
        for pattern, alt, reason in BASH_ALTERNATIVES:
            if pattern.search(command):
                suggestion = f"Consider ~/.claude/scripts/{alt} ({reason})"
                break

    elif ctx.tool_name == "Grep":
        output_mode = ctx.tool_input.output_mode or "files_with_matches"
        if output_mode == "content" and not ctx.tool_input.head_limit:
            suggestion = "Add head_limit to Grep to reduce token usage"

    elif ctx.tool_name == "Read":
        file_path = ctx.tool_input.file_path or ""
        try:
            if file_path and Path(file_path).exists():
                size = Path(file_path).stat().st_size
                if size > 50000:
                    suggestion = "Large file - consider smart-view.sh"
        except Exception:
            pass

    if suggestion:
        return Response.allow(f"[Optimization] {suggestion}")

    return None
