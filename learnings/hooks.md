# Hook Learnings

## [2025-12-25] Async Hooks for Non-Blocking Operations

**Context:** Reviewing agentskills claude-config-example
**Learning:** Shell hooks can run asynchronously by outputting JSON config as the first line: `echo '{"async":true,"asyncTimeout":15000}'`. Hook continues without blocking tool execution.
**Evidence:** agentskills/claude-config-example/hooks/session-start.sh
**Application:** Use for network requests, slow initialization, anything that doesn't need to block. Document in architecture.md.

## [2025-12-25] Dispatcher Pattern Saves ~200ms Per Tool Call

**Context:** Hook architecture optimization
**Learning:** Instead of registering many individual hooks for PreToolUse/PostToolUse, use a single dispatcher that internally routes to handlers. Saves process spawn overhead.
**Evidence:** Measured latency reduction with pre_tool_dispatcher.py and post_tool_dispatcher.py
**Application:** Consolidate hooks by event type into dispatchers. Individual hooks only for different event types.

## [2025-12-25] Graceful Degradation in Hooks

**Context:** Hook reliability patterns
**Learning:** Hooks should never crash Claude Code. Use try/except with fallback to allow/pass. Log errors to hook-events.jsonl for debugging.
**Evidence:** hook_utils.py graceful_main decorator
**Application:** Always wrap hook logic in try/except. Return safe default on error. Never raise unhandled exceptions.

## [2025-12-25] Warning Escalation Pattern

**Context:** TDD guard implementation
**Learning:** Instead of immediately blocking, use escalating warnings: warnings 1-3 allow with count, warning 4+ blocks. Gives user awareness before enforcement.
**Evidence:** Community research on warning fatigue and user experience
**Application:** For non-critical guards, implement warning threshold before blocking. Store count in data/ file with time window.
