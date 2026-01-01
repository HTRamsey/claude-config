"""
Agent Chainer - Suggests follow-up specialists based on Task output.

PostToolUse: Task
"""
import re

import sys
from pathlib import Path
from hooks.config import Limits
from hooks.hook_sdk import PostToolUseContext, Response


# Pre-compiled chain rules for performance
_CHAIN_RULES_RAW = [
    {
        "patterns": [
            r"(?i)(sql injection|xss|csrf|command injection|path traversal)",
            r"(?i)(hardcoded (credential|secret|password|api.?key))",
            r"(?i)(authentication|authorization).*(missing|bypass|vulnerable)",
            r"(?i)(insecure|vulnerable).*(crypto|random|hash)",
            r"(?i)🔴.*security",
        ],
        "agent": "code-reviewer",
        "reason": "Security vulnerability detected - deep security analysis recommended",
    },
    {
        "patterns": [
            r"(?i)(n\+1|n \+ 1).*(query|queries)",
            r"(?i)(memory leak|unbounded|allocation in (hot|loop))",
            r"(?i)O\(n[²2]\)|O\(n\^2\)",
            r"(?i)(performance|slow).*(critical|severe|significant)",
            r"(?i)🟡.*performance",
        ],
        "agent": "code-reviewer",
        "reason": "Performance issue detected - code review with performance focus recommended",
    },
    {
        "patterns": [
            r"(?i)(accessibility|a11y|wcag|aria).*(missing|issue|violation)",
            r"(?i)(screen reader|keyboard).*(navigation|focus|trap)",
            r"(?i)\.(jsx|tsx|vue|svelte|qml):\d+",
        ],
        "agent": "code-reviewer",
        "reason": "UI code or accessibility issue - code review with accessibility focus recommended",
    },
    {
        "patterns": [
            r"(?i)(no test|missing test|untested|test coverage).*(low|none|missing)",
            r"(?i)(edge case|boundary|error handling).*(not|missing|untested)",
        ],
        "agent": "test-generator",
        "reason": "Test gaps detected - test generation recommended",
    },
    {
        "patterns": [
            r"(?i)(unused|dead|orphan).*(function|class|import|variable|code)",
            r"(?i)(deprecated|obsolete).*(still|found|exists)",
        ],
        "agent": "code-reviewer",
        "reason": "Potential dead code - code review for cleanup recommended",
    },
]

CHAIN_RULES = [
    {
        "patterns": [re.compile(p) for p in rule["patterns"]],
        "agent": rule["agent"],
        "reason": rule["reason"],
    }
    for rule in _CHAIN_RULES_RAW
]

CHAINABLE_AGENTS = {"code-reviewer", "Explore", "error-explainer", "quick-lookup"}


def suggest_chain(raw: dict) -> dict | None:
    """Suggest follow-up specialists based on Task output."""
    ctx = PostToolUseContext(raw)
    tool_output = ctx.tool_result.raw

    if ctx.tool_name != "Task":
        return None

    source_agent = ctx.tool_input.subagent_type or ""
    if source_agent not in CHAINABLE_AGENTS:
        return None

    output = ""
    if isinstance(tool_output, dict):
        output = tool_output.get("output", "") or tool_output.get("content", "")
    elif isinstance(tool_output, str):
        output = tool_output

    if not output:
        return None

    recommendations = []
    seen_agents = set()

    for rule in CHAIN_RULES:
        for pattern in rule["patterns"]:
            if pattern.search(output):
                agent = rule["agent"]
                if agent not in seen_agents and agent != source_agent:
                    recommendations.append({"agent": agent, "reason": rule["reason"]})
                    seen_agents.add(agent)
                break

    if recommendations:
        msg_lines = [f"[Agent Chaining] Based on {source_agent} findings:"]
        for rec in recommendations[:Limits.MAX_CHAIN_RECOMMENDATIONS]:
            msg_lines.append(f"  → Task(subagent_type='{rec['agent']}') - {rec['reason']}")
        msg_lines.append("  Use orchestrator for comprehensive multi-agent review.")

        return Response.message("\n".join(msg_lines), event="PostToolUse")

    return None
