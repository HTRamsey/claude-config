#!/usr/bin/env bash
# Setup/update the Claude Code Python venv using uv (with pip fallback)
set -euo pipefail

VENV_DIR="$HOME/.claude/data/venv"
HOOKS_DIR="$HOME/.claude/hooks"
ENV_FILE="$HOME/.claude/.env.local"

# Check if uv is available (10-100x faster than pip)
if command -v uv &>/dev/null; then
    USE_UV=1
else
    USE_UV=0
    echo "Note: Install uv for 10-100x faster installs: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

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

do_install() {
    local pkg="$1"
    local quiet="${2:-1}"
    if [[ $USE_UV -eq 1 ]]; then
        if [[ $quiet -eq 1 ]]; then
            uv pip install --quiet --python "$VENV_DIR/bin/python3" "$pkg"
        else
            uv pip install --python "$VENV_DIR/bin/python3" "$pkg"
        fi
    else
        if [[ $quiet -eq 1 ]]; then
            "$VENV_DIR/bin/pip" install --quiet "$pkg"
        else
            "$VENV_DIR/bin/pip" install "$pkg"
        fi
    fi
}

case "${1:-update}" in
    create)
        echo "Creating venv at $VENV_DIR..."
        if [[ $USE_UV -eq 1 ]]; then
            uv venv "$VENV_DIR"
        else
            python3 -m venv "$VENV_DIR"
            "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        fi
        if [[ -f "$HOOKS_DIR/pyproject.toml" ]]; then
            do_install "$HOOKS_DIR"
        fi
        init_env_file
        echo "Done. Venv ready."
        ;;
    update)
        [ ! -d "$VENV_DIR" ] && exec "$0" create
        echo "Updating venv..."
        if [[ $USE_UV -eq 0 ]]; then
            "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        fi
        if [[ -f "$HOOKS_DIR/pyproject.toml" ]]; then
            do_install "$HOOKS_DIR"
        fi
        echo "Done."
        ;;
    check)
        if [ -d "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python3" ]; then
            echo "✓ Venv exists: $VENV_DIR"
            echo "  Using: $(command -v uv &>/dev/null && echo 'uv' || echo 'pip')"
            "$VENV_DIR/bin/python3" --version
            if [[ $USE_UV -eq 1 ]]; then
                uv pip list --python "$VENV_DIR/bin/python3" 2>/dev/null | head -10
            else
                "$VENV_DIR/bin/pip" list --format=freeze 2>/dev/null | head -10
            fi
        else
            echo "✗ Venv not found at $VENV_DIR"
            exit 1
        fi
        ;;
    dev)
        # Install with dev dependencies
        [ ! -d "$VENV_DIR" ] && exec "$0" create
        echo "Installing with dev dependencies..."
        do_install "$HOOKS_DIR[dev]"
        echo "Done."
        ;;
    sync)
        # Sync from lock file (uv only)
        if [[ $USE_UV -eq 0 ]]; then
            echo "Error: 'sync' requires uv"
            exit 1
        fi
        [ ! -d "$VENV_DIR" ] && uv venv "$VENV_DIR"
        echo "Syncing from pyproject.toml..."
        (cd "$HOOKS_DIR" && uv sync --python "$VENV_DIR/bin/python3")
        echo "Done."
        ;;
    lock)
        # Generate lock file (uv only)
        if [[ $USE_UV -eq 0 ]]; then
            echo "Error: 'lock' requires uv"
            exit 1
        fi
        echo "Generating uv.lock..."
        (cd "$HOOKS_DIR" && uv lock)
        echo "Done. Created $HOOKS_DIR/uv.lock"
        ;;
    init-env)
        init_env_file
        ;;
    *)
        echo "Usage: $0 {create|update|check|dev|sync|lock|init-env}"
        echo ""
        echo "Commands:"
        echo "  create   - Create new venv and install dependencies"
        echo "  update   - Update existing venv with latest dependencies"
        echo "  check    - Check venv status and list packages"
        echo "  dev      - Install with dev dependencies (pytest, etc.)"
        echo "  sync     - Sync from uv.lock (uv only, reproducible)"
        echo "  lock     - Generate uv.lock from pyproject.toml (uv only)"
        echo "  init-env - Create .env.local for queue API mode"
        exit 1
        ;;
esac
