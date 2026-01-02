#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SessionEnd Dispatcher - Consolidated SessionEnd hooks.

Handlers (now in handlers/):
- session_persistence: Auto-save session insights to memory MCP
- transcript_converter: Convert JSONL transcripts to readable JSON

Runs on SessionEnd event to capture learnings before conversation ends.
"""
import subprocess
from pathlib import Path

from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers import session_persistence, transcript_converter
from hooks.hook_utils import get_session_id, log_event


class SessionEndDispatcher(SimpleDispatcher):
    """SessionEnd event dispatcher."""

    DISPATCHER_NAME = "session_end_handler"
    EVENT_TYPE = None  # SessionEnd doesn't have event_type in context

    def handle(self, ctx: dict) -> list[str]:
        messages = []

        # Clean up old session files
        cleaned = session_persistence.cleanup_old_session_files(max_age_hours=24)
        if cleaned > 0:
            messages.append(f"[Session Cleanup] Removed {cleaned} old session files")

        transcript_path = ctx.get("transcript_path", "")
        session_id = get_session_id(ctx)

        # Extract information from transcript
        info = session_persistence.extract_project_info(transcript_path)

        # Save session metadata for better resumption
        session_persistence.save_session_metadata(session_id, info, transcript_path)

        # Skip memory suggestions if minimal activity
        total_tool_uses = sum(info.get("tools_used", {}).values())
        if total_tool_uses >= 5:
            suggestions = session_persistence.generate_memory_suggestions(info)
            if suggestions.get("entities"):
                messages.extend(session_persistence.format_memory_suggestions(suggestions))

        # Run transcript converter if enabled
        converted = transcript_converter.run_converter()
        if converted:
            messages.append(f"[Transcript Converter] Converted {len(converted)} transcript(s)")

        # Update usage cache for statusline
        self._update_usage_cache()

        return messages

    def _update_usage_cache(self) -> None:
        """Update usage cache for statusline."""
        usage_script = Path.home() / ".claude/scripts/diagnostics/usage-stats.py"
        if usage_script.exists():
            try:
                subprocess.run(
                    [str(usage_script), "--update-cache"],
                    capture_output=True,
                    timeout=10
                )
            except subprocess.TimeoutExpired:
                log_event(self.DISPATCHER_NAME, "usage_cache_timeout", {
                    "script": str(usage_script)
                }, "warning")
            except OSError as e:
                log_event(self.DISPATCHER_NAME, "usage_cache_error", {
                    "script": str(usage_script),
                    "error": str(e)
                }, "warning")


if __name__ == "__main__":
    SessionEndDispatcher().run()
