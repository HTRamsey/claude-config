"""
Suggestions package - Unified suggestion system for Claude Code.

Decomposed from suggestion_engine.py for better modularity and
independent disable/enable control.

Modules:
- skill_suggester: Suggests creator skills for config files
- subagent_suggester: Suggests agent delegation for exploration
- tool_optimizer: Suggests better tool alternatives
- agent_chainer: Suggests follow-up specialists after Task
"""

from hooks.suggestions.skill_suggester import suggest_skill
from hooks.suggestions.subagent_suggester import suggest_subagent
from hooks.suggestions.tool_optimizer import suggest_optimization
from hooks.suggestions.agent_chainer import suggest_chain
from hooks.suggestions.shared import get_state, update_state, save_state

__all__ = [
    "suggest_skill",
    "suggest_subagent",
    "suggest_optimization",
    "suggest_chain",
    "get_state",
    "update_state",
    "save_state",
]
