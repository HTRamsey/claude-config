#!/usr/bin/env bash
# Setup/update the Claude Code Python venv
set -e

VENV_DIR="$HOME/.claude/venv"
HOOKS_DIR="$HOME/.claude/hooks"

case "${1:-update}" in
    create)
        echo "Creating venv at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        if [[ -f "$HOOKS_DIR/pyproject.toml" ]]; then
            "$VENV_DIR/bin/pip" install --quiet "$HOOKS_DIR"
        fi
        echo "Done. Venv ready."
        ;;
    update)
        [ ! -d "$VENV_DIR" ] && exec "$0" create
        echo "Updating venv..."
        "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        if [[ -f "$HOOKS_DIR/pyproject.toml" ]]; then
            "$VENV_DIR/bin/pip" install --quiet --upgrade "$HOOKS_DIR"
        fi
        echo "Done."
        ;;
    check)
        if [ -d "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python3" ]; then
            echo "✓ Venv exists: $VENV_DIR"
            "$VENV_DIR/bin/python3" --version
            "$VENV_DIR/bin/pip" list --format=freeze 2>/dev/null | head -10
        else
            echo "✗ Venv not found at $VENV_DIR"
            exit 1
        fi
        ;;
    dev)
        # Install with dev dependencies
        [ ! -d "$VENV_DIR" ] && exec "$0" create
        echo "Installing with dev dependencies..."
        "$VENV_DIR/bin/pip" install --quiet "$HOOKS_DIR[dev]"
        echo "Done."
        ;;
    *)
        echo "Usage: $0 {create|update|check|dev}"
        exit 1
        ;;
esac
