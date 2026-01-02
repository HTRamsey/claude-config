#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentLifecycle hook - tracks subagent lifecycle for metrics, timing, and usage.
Called via pre_tool_dispatcher (handle_start) and post_tool_dispatcher (handle_complete)
for Task tool invocations.

Also maintains Reflexion memory - a log of task outcomes and lessons
for learning from past subagent executions.

Consolidates usage_tracker functionality for Task and Skill tools.
"""
import hashlib
from datetime import datetime
from pathlib import Path

from hooks.hook_utils import (
    log_event,
    get_session_state,
    update_session_state,
    safe_load_json,
    atomic_write_json,
    record_usage,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext

REFLEXION_LOG = Path.home() / ".claude/data/reflexion-log.json"
CONFIDENCE_FILE = Path.home() / ".claude/data/agent-confidence.json"
MAX_REFLEXION_ENTRIES = 100  # Keep last N entries


def load_reflexion_log() -> list:
    """Load the reflexion log."""
    data = safe_load_json(REFLEXION_LOG, [])
    return data if isinstance(data, list) else []


def save_reflexion_log(entries: list):
    """Save the reflexion log, trimming old entries."""
    # Keep only last N entries
    trimmed = entries[-MAX_REFLEXION_ENTRIES:]
    if not atomic_write_json(REFLEXION_LOG, trimmed):
        log_event("subagent_lifecycle", "reflexion_save_error", {"error": "Failed to save reflexion log"})


def load_confidence_data() -> dict:
    """Load confidence tracking data."""
    return safe_load_json(CONFIDENCE_FILE, {"agents": {}, "updated": None})


def save_confidence_data(data: dict):
    """Save confidence tracking data."""
    from datetime import datetime
    data["updated"] = datetime.now().isoformat()
    atomic_write_json(CONFIDENCE_FILE, data)


def update_confidence(subagent_type: str, outcome: str):
    """Update confidence scores based on outcome.

    Confidence = success_count / usage_count
    Tracks per-agent success rates for pattern learning.
    """
    if outcome == "unknown":
        return  # Don't count unknown outcomes

    data = load_confidence_data()
    agents = data.get("agents", {})

    if subagent_type not in agents:
        agents[subagent_type] = {
            "usage_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "confidence": 0.0
        }

    agent = agents[subagent_type]
    agent["usage_count"] += 1

    if outcome == "success":
        agent["success_count"] += 1
    elif outcome == "failure":
        agent["failure_count"] += 1

    # Calculate confidence (success rate)
    if agent["usage_count"] > 0:
        agent["confidence"] = round(agent["success_count"] / agent["usage_count"], 3)

    data["agents"] = agents
    save_confidence_data(data)


def get_agent_confidence(subagent_type: str) -> float:
    """Get confidence score for an agent type."""
    data = load_confidence_data()
    agent = data.get("agents", {}).get(subagent_type, {})
    return agent.get("confidence", 0.0)


def extract_task_summary(raw: dict) -> str:
    """Extract a summary of the task from context."""
    tool_input = raw.get("tool_input", {})
    # Try to get from prompt or description
    prompt = tool_input.get("prompt", raw.get("prompt", ""))
    description = tool_input.get("description", raw.get("description", ""))

    summary = description or prompt[:100]
    if len(prompt) > 100 and not description:
        summary += "..."
    return summary


def extract_outcome(raw: dict) -> str:
    """Determine outcome from stop_reason and context."""
    stop_reason = raw.get("stop_reason", "")

    if stop_reason == "completed":
        return "success"
    elif stop_reason in ("error", "failed"):
        return "failure"
    elif stop_reason == "interrupted":
        return "interrupted"
    else:
        return "unknown"


def extract_lessons(raw: dict, outcome: str) -> list:
    """Extract lessons learned from the task output."""
    lessons = []
    output = raw.get("tool_output", "") or raw.get("output", "") or raw.get("result", "")

    # For failures, try to extract what went wrong
    if outcome == "failure":
        if "timeout" in output.lower():
            lessons.append("Task timed out - consider breaking into smaller parts")
        if "not found" in output.lower():
            lessons.append("File or resource not found - verify paths before dispatching")
        if "permission" in output.lower():
            lessons.append("Permission issue - check access rights")

    # For successes, note patterns
    if outcome == "success":
        if "test" in output.lower() and "pass" in output.lower():
            lessons.append("Tests passed - approach validated")
        if "refactor" in output.lower():
            lessons.append("Refactoring completed successfully")

    return lessons


def record_reflexion(raw: dict, duration_s: float | None):
    """Record a reflexion entry for this subagent completion."""
    tool_input = raw.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", raw.get("subagent_type", "unknown"))
    prompt = tool_input.get("prompt", raw.get("prompt", ""))

    # Create a hash of the task for deduplication
    task_hash = hashlib.md5(
        f"{subagent_type}:{prompt[:200]}".encode()
    ).hexdigest()[:12]

    outcome = extract_outcome(raw)
    lessons = extract_lessons(raw, outcome)

    # Update confidence tracking
    update_confidence(subagent_type, outcome)
    confidence = get_agent_confidence(subagent_type)

    entry = {
        "task_hash": task_hash,
        "subagent_type": subagent_type,
        "task_summary": extract_task_summary(raw),
        "outcome": outcome,
        "confidence": confidence,
        "lessons": lessons,
        "duration_s": duration_s,
        "timestamp": datetime.now().isoformat()
    }

    # Only record if there's meaningful content
    if entry["task_summary"] or lessons:
        log = load_reflexion_log()
        log.append(entry)
        save_reflexion_log(log)

        log_event("subagent_lifecycle", "reflexion_recorded", {
            "task_hash": task_hash,
            "outcome": outcome,
            "confidence": confidence,
            "lesson_count": len(lessons)
        })


def handle_start(raw: dict):
    """Handle Task tool PreToolUse - track spawn time, counts, and usage."""
    ctx = PreToolUseContext(raw)
    subagent_type = ctx.tool_input.subagent_type or raw.get("subagent_type", "unknown")
    subagent_id = raw.get("subagent_id", ctx.tool_use_id or "")

    # Record usage for stats tracking
    if subagent_type:
        record_usage("agents", subagent_type)

    state = get_session_state()

    # Track active subagents with their start times
    active_subagents = state.get("active_subagents", {})
    active_subagents[subagent_id] = {
        "type": subagent_type,
        "started_at": datetime.now().isoformat()
    }

    # Track spawn counts per type
    spawn_counts = state.get("subagent_spawn_counts", {})
    spawn_counts[subagent_type] = spawn_counts.get(subagent_type, 0) + 1

    update_session_state({
        "active_subagents": active_subagents,
        "subagent_spawn_counts": spawn_counts
    })

    log_event("subagent_start", "success", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "spawn_count": spawn_counts[subagent_type]
    })


def handle_skill(raw: dict):
    """Handle Skill tool PreToolUse - track skill usage."""
    tool_input = raw.get("tool_input", {})
    skill_name = tool_input.get("skill", "")
    if skill_name:
        record_usage("skills", skill_name)


def handle_complete(raw: dict):
    """Handle Task tool PostToolUse - track completion and calculate duration."""
    ctx = PostToolUseContext(raw)
    subagent_type = ctx.tool_input.subagent_type or raw.get("subagent_type", "unknown")
    subagent_id = raw.get("subagent_id", ctx.tool_use_id or "")
    stop_reason = raw.get("stop_reason", "completed" if ctx.tool_result.success else "error")

    state = get_session_state()
    subagent_stats = state.get("subagent_stats", {})

    if subagent_type not in subagent_stats:
        subagent_stats[subagent_type] = {"count": 0, "last_run": None, "total_duration_s": 0}

    subagent_stats[subagent_type]["count"] += 1
    subagent_stats[subagent_type]["last_run"] = datetime.now().isoformat()

    # Calculate duration if we have start time from SubagentStart hook
    duration_s = None
    active_subagents = state.get("active_subagents", {})
    if subagent_id in active_subagents:
        try:
            started_at = datetime.fromisoformat(active_subagents[subagent_id]["started_at"])
            duration_s = (datetime.now() - started_at).total_seconds()
            subagent_stats[subagent_type]["total_duration_s"] = \
                subagent_stats[subagent_type].get("total_duration_s", 0) + duration_s
        except (ValueError, KeyError):
            pass
        # Clean up active subagent entry
        del active_subagents[subagent_id]

    update_session_state({
        "subagent_stats": subagent_stats,
        "active_subagents": active_subagents
    })

    log_event("subagent_complete", "success", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "stop_reason": stop_reason,
        "duration_s": duration_s,
        "total_runs": subagent_stats[subagent_type]["count"]
    })

    # Record to Reflexion memory
    record_reflexion(raw, duration_s)
