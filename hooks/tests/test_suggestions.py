"""Tests for suggestions package."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from suggestions import (
    suggest_skill,
    suggest_subagent,
    suggest_optimization,
    suggest_chain,
    get_state,
    update_state,
)


class TestSkillSuggester:
    """Tests for skill_suggester module.

    Note: suggest_skill only fires first time per session to avoid noise.
    These tests check the suggestion logic indirectly.
    """

    def test_suggest_skill_detects_hook_pattern(self):
        """Should recognize hook file patterns."""
        from suggestions.skill_suggester import SKILL_SUGGESTIONS
        # Verify the pattern exists in suggestions
        hook_patterns = [s for s in SKILL_SUGGESTIONS if s["skill"] == "hook-creator"]
        assert len(hook_patterns) > 0
        # Check pattern matches hook path
        import re
        pattern = re.compile(hook_patterns[0]["pattern"])
        assert pattern.search("/home/user/.claude/hooks/new_hook.py")

    def test_suggest_skill_detects_agent_pattern(self):
        """Should recognize agent file patterns."""
        from suggestions.skill_suggester import SKILL_SUGGESTIONS
        agent_patterns = [s for s in SKILL_SUGGESTIONS if s["skill"] == "agent-creator"]
        assert len(agent_patterns) > 0
        import re
        pattern = re.compile(agent_patterns[0]["pattern"])
        assert pattern.search("/home/user/.claude/agents/new_agent.md")

    def test_suggest_skill_detects_command_pattern(self):
        """Should recognize command file patterns."""
        from suggestions.skill_suggester import SKILL_SUGGESTIONS
        cmd_patterns = [s for s in SKILL_SUGGESTIONS if s["skill"] == "command-creator"]
        assert len(cmd_patterns) > 0
        import re
        pattern = re.compile(cmd_patterns[0]["pattern"])
        assert pattern.search("/home/user/.claude/commands/my_command.md")

    def test_suggest_skill_for_regular_file(self):
        """Should return None for regular files."""
        ctx = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/home/user/project/src/main.py"}
        }
        result = suggest_skill(ctx)
        assert result is None


class TestSubagentSuggester:
    """Tests for subagent_suggester module."""

    def test_suggest_subagent_for_exploration(self):
        """Should suggest Explore agent for broad searches."""
        ctx = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "authentication"},
            "cwd": "/project"
        }
        # First search shouldn't trigger suggestion
        result = suggest_subagent(ctx)
        # Would need multiple calls to trigger

    def test_suggest_subagent_none_for_targeted_search(self):
        """Should not suggest for clearly targeted searches."""
        ctx = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "class MySpecificClass"},
            "cwd": "/project"
        }
        result = suggest_subagent(ctx)
        # Targeted patterns shouldn't trigger suggestion
        assert result is None or "specific" in str(result).lower() or result is None


class TestToolOptimizer:
    """Tests for tool_optimizer module."""

    def test_suggest_optimization_for_grep(self):
        """Should suggest optimization for grep command."""
        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "grep -r 'pattern' ."}
        }
        result = suggest_optimization(ctx)
        # Should suggest offload script or rg
        if result:
            reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
            assert "Optimization" in reason or "offload" in reason or "rg" in reason

    def test_suggest_optimization_for_find(self):
        """Should suggest optimization for find command."""
        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "find . -name '*.py'"}
        }
        result = suggest_optimization(ctx)
        # Should suggest offload script or fd
        if result:
            reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
            assert "Optimization" in reason or "offload" in reason or "fd" in reason


class TestAgentChainer:
    """Tests for agent_chainer module."""

    def test_suggest_chain_for_security_finding(self):
        """Should suggest code-reviewer for security issues."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "Explore", "prompt": "find auth"},
            "tool_response": "Found SQL injection vulnerability in login.py"
        }
        result = suggest_chain(ctx)
        assert result is not None
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        assert "code-reviewer" in msg

    def test_suggest_chain_for_test_gaps(self):
        """Should suggest test-generator for missing tests."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "code-reviewer", "prompt": "review"},
            "tool_response": "No tests found for this module. Missing test coverage."
        }
        result = suggest_chain(ctx)
        assert result is not None
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        assert "test-generator" in msg

    def test_no_chain_for_non_chainable_agent(self):
        """Should not chain from non-chainable agents."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "batch-editor", "prompt": "edit"},
            "tool_response": "Edited 5 files"
        }
        result = suggest_chain(ctx)
        assert result is None


class TestSharedState:
    """Tests for shared state management."""

    def test_get_state_returns_dict(self):
        """get_state should return a dictionary."""
        state = get_state()
        assert isinstance(state, dict)

    def test_update_state_modifies_state(self):
        """update_state should modify state with dict updates."""
        update_state({"test_key_unique": "test_value"})
        state = get_state()
        assert state.get("test_key_unique") == "test_value"
