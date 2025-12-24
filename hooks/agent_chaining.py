#!/home/jonglaser/.claude/venv/bin/python3
"""
Agent Chaining Hook - Automatic specialist escalation based on findings.

PostToolUse hook for Task that parses agent output and suggests
follow-up specialists when specific patterns are detected.
"""
import json
import sys
import re
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


# Chain rules: pattern in output → recommended agent
CHAIN_RULES = [
    # Security escalation
    {
        "patterns": [
            r"(?i)(sql injection|xss|csrf|command injection|path traversal)",
            r"(?i)(hardcoded (credential|secret|password|api.?key))",
            r"(?i)(authentication|authorization).*(missing|bypass|vulnerable)",
            r"(?i)(insecure|vulnerable).*(crypto|random|hash)",
            r"(?i)🔴.*security",
        ],
        "agent": "security-reviewer",
        "reason": "Security vulnerability detected - deep security analysis recommended",
    },
    # Performance escalation
    {
        "patterns": [
            r"(?i)(n\+1|n \+ 1).*(query|queries)",
            r"(?i)(memory leak|unbounded|allocation in (hot|loop))",
            r"(?i)O\(n[²2]\)|O\(n\^2\)",
            r"(?i)(performance|slow).*(critical|severe|significant)",
            r"(?i)🟡.*performance",
        ],
        "agent": "perf-reviewer",
        "reason": "Performance issue detected - deep performance analysis recommended",
    },
    # Accessibility escalation (UI code)
    {
        "patterns": [
            r"(?i)(accessibility|a11y|wcag|aria).*(missing|issue|violation)",
            r"(?i)(screen reader|keyboard).*(navigation|focus|trap)",
            r"(?i)\.(jsx|tsx|vue|svelte|qml):\d+",  # UI file extensions
        ],
        "agent": "accessibility-reviewer",
        "reason": "UI code or accessibility issue - accessibility review recommended",
    },
    # Test generation
    {
        "patterns": [
            r"(?i)(no test|missing test|untested|test coverage).*(low|none|missing)",
            r"(?i)(edge case|boundary|error handling).*(not|missing|untested)",
        ],
        "agent": "test-generator",
        "reason": "Test gaps detected - test generation recommended",
    },
    # Dead code detection
    {
        "patterns": [
            r"(?i)(unused|dead|orphan).*(function|class|import|variable|code)",
            r"(?i)(deprecated|obsolete).*(still|found|exists)",
        ],
        "agent": "dead-code-finder",
        "reason": "Potential dead code - cleanup analysis recommended",
    },
]

# Agents that should trigger chaining (reviewers/analyzers)
CHAINABLE_AGENTS = {
    "code-reviewer",
    "quick-explorer",
    "Explore",
    "error-explainer",
}


def parse_agent_output(output: str) -> list:
    """Check output for chain trigger patterns."""
    recommendations = []
    seen_agents = set()

    for rule in CHAIN_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, output):
                agent = rule["agent"]
                if agent not in seen_agents:
                    recommendations.append({
                        "agent": agent,
                        "reason": rule["reason"],
                    })
                    seen_agents.add(agent)
                break  # One match per rule is enough

    return recommendations


def get_source_agent(tool_input: dict) -> str:
    """Extract the source agent type from Task input."""
    return tool_input.get("subagent_type", "")


@graceful_main("agent_chaining")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    # Try both field names for compatibility
    tool_output = ctx.get("tool_result", ctx.get("tool_response", {}))

    # Only process Task tool completions
    if tool_name != "Task":
        sys.exit(0)

    # Get the agent that just ran
    source_agent = get_source_agent(tool_input)

    # Only chain from analysis/review agents
    if source_agent not in CHAINABLE_AGENTS:
        sys.exit(0)

    # Get the output content
    output = ""
    if isinstance(tool_output, dict):
        output = tool_output.get("output", "") or tool_output.get("content", "")
    elif isinstance(tool_output, str):
        output = tool_output

    if not output:
        sys.exit(0)

    # Check for chain triggers
    recommendations = parse_agent_output(output)

    # Don't recommend the same agent that just ran
    recommendations = [r for r in recommendations if r["agent"] != source_agent]

    if recommendations:
        msg_lines = [f"[Agent Chaining] Based on {source_agent} findings:"]
        for rec in recommendations[:2]:  # Max 2 recommendations
            msg_lines.append(f"  → Task(subagent_type='{rec['agent']}') - {rec['reason']}")
        msg_lines.append("  Use orchestrator for comprehensive multi-agent review.")

        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": "\n".join(msg_lines)
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
