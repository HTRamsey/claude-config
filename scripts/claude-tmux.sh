#!/usr/bin/env bash
# claude-tmux.sh - Multi-pane Claude Code workspace
#
# Usage: claude-tmux.sh [project-path]
#
# Layout:
#  ┌──────────┬──────────┐
#  │  Claude  │  Claude  │
#  │  (main)  │ (review) │
#  ├──────────┴──────────┤
#  │   Build / Tests     │
#  └─────────────────────┘

SESSION="claude-dev"
PROJECT="${1:-$(pwd)}"

# Check if tmux is installed
if ! command -v tmux &>/dev/null; then
    echo "Error: tmux is required but not installed" >&2
    echo "Install with: apt install tmux (Debian/Ubuntu) or brew install tmux (macOS)" >&2
    exit 1
fi

# Kill existing session if exists
tmux kill-session -t "$SESSION" 2>/dev/null

# Create session with first pane (main Claude)
tmux new-session -d -s "$SESSION" -c "$PROJECT"
tmux rename-window -t "$SESSION:0" "claude"

# Right pane - second Claude instance
tmux split-window -h -t "$SESSION:0" -c "$PROJECT"

# Bottom pane - build/test watcher (25% height)
tmux split-window -v -t "$SESSION:0.0" -c "$PROJECT" -p 25

# Merge bottom across both columns
tmux select-layout -t "$SESSION:0" main-horizontal

# Start commands in each pane
tmux send-keys -t "$SESSION:0.0" "claude" Enter
tmux send-keys -t "$SESSION:0.1" "# Ready for: claude (review/tests)" Enter
tmux send-keys -t "$SESSION:0.2" "# Build watcher: npm run dev / make watch / pytest --watch" Enter

# Focus main pane
tmux select-pane -t "$SESSION:0.0"

# Attach
tmux attach-session -t "$SESSION"
