#!/usr/bin/env bash
# dependency-graph.sh - Generate dependency graph for Claude Code config
#
# Usage:
#   dependency-graph.sh [--format mermaid|dot] [--type hooks|scripts|all]
#
# Analyzes:
#   - Python imports in hooks/*.py
#   - source statements in scripts/**/*.sh
#   - Handler references in dispatchers
#
# Output: Mermaid or DOT graph format

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

FORMAT="mermaid"
TYPE="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --type)
            TYPE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: dependency-graph.sh [--format mermaid|dot] [--type hooks|scripts|all]"
            echo ""
            echo "Generates dependency graph for Claude Code configuration."
            echo ""
            echo "Options:"
            echo "  --format  Output format: mermaid (default) or dot"
            echo "  --type    What to analyze: hooks, scripts, or all (default)"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Collect edges
declare -a EDGES=()

# Analyze Python hook imports
analyze_hooks() {
    local hooks_dir="$CLAUDE_DIR/hooks"
    [[ -d "$hooks_dir" ]] || return

    for hook in "$hooks_dir"/*.py; do
        [[ -f "$hook" ]] || continue
        local name=$(basename "$hook" .py)

        # Skip __pycache__ and non-hook files
        [[ "$name" == "__pycache__" ]] && continue

        # Find local imports (from same directory)
        while IFS= read -r import; do
            # Extract module name from "from X import" or "import X"
            local module=""
            if [[ "$import" =~ ^from[[:space:]]+([a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]+import ]]; then
                module="${BASH_REMATCH[1]}"
            elif [[ "$import" =~ ^import[[:space:]]+([a-zA-Z_][a-zA-Z0-9_]*) ]]; then
                module="${BASH_REMATCH[1]}"
            fi

            # Only include if it's a local hook file
            if [[ -n "$module" ]] && [[ -f "$hooks_dir/$module.py" ]]; then
                EDGES+=("hook:$name|hook:$module")
            fi
        done < <(grep -E "^(from|import) [a-z_]+" "$hook" 2>/dev/null || true)
    done

    # Analyze dispatcher references
    for dispatcher in "$hooks_dir"/*_dispatcher.py; do
        [[ -f "$dispatcher" ]] || continue
        local dname=$(basename "$dispatcher" .py)

        # Find handler imports
        while IFS= read -r line; do
            if [[ "$line" =~ from[[:space:]]+([a-zA-Z_]+)[[:space:]]+import ]]; then
                local handler="${BASH_REMATCH[1]}"
                if [[ -f "$hooks_dir/$handler.py" ]]; then
                    EDGES+=("hook:$dname|hook:$handler")
                fi
            fi
        done < <(grep "from .* import" "$dispatcher" 2>/dev/null || true)
    done
}

# Analyze shell script sources
analyze_scripts() {
    local scripts_dir="$CLAUDE_DIR/scripts"
    [[ -d "$scripts_dir" ]] || return

    while IFS= read -r script; do
        [[ -f "$script" ]] || continue
        local rel_path="${script#$scripts_dir/}"
        local name="${rel_path//\//_}"
        name="${name%.sh}"

        # Find source statements
        while IFS= read -r line; do
            # Match: source "path" or . "path" or source $VAR/path
            local sourced=""
            if [[ "$line" =~ source[[:space:]]+[\"\']?([^\"\'\;]+) ]]; then
                sourced="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^\.[[:space:]]+[\"\']?([^\"\'\;]+) ]]; then
                sourced="${BASH_REMATCH[1]}"
            fi

            if [[ -n "$sourced" ]]; then
                # Normalize path
                sourced="${sourced//\$SCRIPT_DIR/../}"
                sourced="${sourced//\$HOME\/\.claude/$CLAUDE_DIR}"
                sourced="${sourced//\~\/\.claude/$CLAUDE_DIR}"

                # Extract just the filename for the edge
                local target=$(basename "$sourced" .sh)
                target="${target//\//_}"

                # Only add if it's a known script
                if [[ "$sourced" == *"lib/"* ]] || [[ "$sourced" == *"common"* ]]; then
                    EDGES+=("script:$name|script:lib_$target")
                fi
            fi
        done < <(grep -E "^[[:space:]]*(source|\.) " "$script" 2>/dev/null || true)
    done < <(find "$scripts_dir" -name "*.sh" -type f 2>/dev/null)
}

# Analyze agent references
analyze_agents() {
    local agents_dir="$CLAUDE_DIR/agents"
    [[ -d "$agents_dir" ]] || return

    # Check which agents are referenced in dispatchers or settings
    for agent in "$agents_dir"/*.md; do
        [[ -f "$agent" ]] || continue
        local name=$(basename "$agent" .md)

        # Check if referenced in post_tool_dispatcher
        if grep -q "\"$name\"" "$CLAUDE_DIR/hooks/post_tool_dispatcher.py" 2>/dev/null; then
            EDGES+=("hook:post_tool_dispatcher|agent:$name")
        fi
        if grep -q "\"$name\"" "$CLAUDE_DIR/hooks/pre_tool_dispatcher.py" 2>/dev/null; then
            EDGES+=("hook:pre_tool_dispatcher|agent:$name")
        fi
    done
}

# Generate Mermaid output
output_mermaid() {
    echo "graph TD"
    echo "    %% Claude Code Dependency Graph"
    echo "    %% Generated: $(date -Iseconds)"
    echo ""

    # Group by type
    echo "    subgraph Hooks"
    for edge in "${EDGES[@]}"; do
        if [[ "$edge" == hook:*\|hook:* ]]; then
            local from="${edge%%|*}"
            local to="${edge##*|}"
            from="${from#hook:}"
            to="${to#hook:}"
            echo "        $from --> $to"
        fi
    done
    echo "    end"
    echo ""

    echo "    subgraph Scripts"
    for edge in "${EDGES[@]}"; do
        if [[ "$edge" == script:*\|script:* ]]; then
            local from="${edge%%|*}"
            local to="${edge##*|}"
            from="${from#script:}"
            to="${to#script:}"
            echo "        $from --> $to"
        fi
    done
    echo "    end"
    echo ""

    # Cross-type edges
    for edge in "${EDGES[@]}"; do
        if [[ "$edge" == hook:*\|agent:* ]]; then
            local from="${edge%%|*}"
            local to="${edge##*|}"
            from="${from#hook:}"
            to="${to#agent:}"
            echo "    $from -.-> $to"
        fi
    done
}

# Generate DOT output
output_dot() {
    echo "digraph ClaudeConfig {"
    echo "    rankdir=LR;"
    echo "    node [shape=box];"
    echo ""

    # Define subgraphs
    echo "    subgraph cluster_hooks {"
    echo "        label=\"Hooks\";"
    echo "        style=filled;"
    echo "        color=lightblue;"
    for edge in "${EDGES[@]}"; do
        if [[ "$edge" == hook:* ]]; then
            local from="${edge%%|*}"
            from="${from#hook:}"
            echo "        \"$from\" [label=\"$from\"];"
        fi
    done
    echo "    }"
    echo ""

    echo "    subgraph cluster_scripts {"
    echo "        label=\"Scripts\";"
    echo "        style=filled;"
    echo "        color=lightgreen;"
    for edge in "${EDGES[@]}"; do
        if [[ "$edge" == script:* ]]; then
            local from="${edge%%|*}"
            from="${from#script:}"
            echo "        \"$from\" [label=\"$from\"];"
        fi
    done
    echo "    }"
    echo ""

    # Edges
    for edge in "${EDGES[@]}"; do
        local from="${edge%%|*}"
        local to="${edge##*|}"
        from="${from#*:}"
        to="${to#*:}"
        echo "    \"$from\" -> \"$to\";"
    done

    echo "}"
}

# Main
case "$TYPE" in
    hooks)
        analyze_hooks
        ;;
    scripts)
        analyze_scripts
        ;;
    all)
        analyze_hooks
        analyze_scripts
        analyze_agents
        ;;
esac

# Output
case "$FORMAT" in
    mermaid)
        output_mermaid
        ;;
    dot)
        output_dot
        ;;
    *)
        echo "Unknown format: $FORMAT" >&2
        exit 1
        ;;
esac

# Summary
echo ""
echo "# Summary: ${#EDGES[@]} dependencies found"
