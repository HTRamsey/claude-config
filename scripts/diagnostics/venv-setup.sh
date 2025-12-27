#!/usr/bin/env bash
# Setup/update the Claude Code Python venv
set -euo pipefail

VENV_DIR="$HOME/.claude/data/venv"
HOOKS_DIR="$HOME/.claude/hooks"
ENV_FILE="$HOME/.claude/.env.local"

init_env_file() {
    if [[ -f "$ENV_FILE" ]]; then
        return 0
    fi
    echo "Creating $ENV_FILE with defaults..."
    cat > "$ENV_FILE" << 'EOF'
# Claude Code local environment - sourced by queue scripts
# chmod 600 this file

# Anthropic API key for queue API mode
export ANTHROPIC_API_KEY=""

# API base URL (uncomment to use proxy or alternative endpoint)
# export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Set to 1 to enable API mode (default: 0 to prevent accidental spend)
export QUEUE_ENABLE_API=0
EOF
    chmod 600 "$ENV_FILE"
    echo "Created $ENV_FILE (edit to add your API key)"
}

case "${1:-update}" in
    create)
        echo "Creating venv at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        if [[ -f "$HOOKS_DIR/pyproject.toml" ]]; then
            "$VENV_DIR/bin/pip" install --quiet "$HOOKS_DIR"
        fi
        init_env_file
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
    init-env)
        init_env_file
        ;;
    *)
        echo "Usage: $0 {create|update|check|dev|init-env}"
        exit 1
        ;;
esac
