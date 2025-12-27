#!/usr/bin/env bash
set -euo pipefail
# Claude Code Status Line (v2.0.70+)
#
# Format: v2.0.76 | path | branch[•N] | Model | terse | 45% ⚡99% ⚠️ | +50/-10 | 79K↓ 68K↑ 5K/m | 10m API:15% | ⏱4h32m
#
# Sections (logically grouped):
#   1. Version: v2.0.76 - Claude Code version
#   2. Path:    ~/project or subdir/ if in project subdirectory
#   3. Git:     branch[~2+1-1•3] - branch name + status indicators
#   4. Model:   Opus 4.5, Sonnet, Haiku
#   5. Style:   terse - output style
#   6. Context: 45% ⚡99% ⚠️ - usage %, cache % of context, 200K warning
#   7. Output:  +50/-10 - lines added/removed
#   8. Tokens:  79K↓ 68K↑ 5K/m - input↓, output↑, rate per minute
#   9. Time:    10m API:15% - duration + API latency %
#  10. Block:   ⏱4h32m - 5-hour billing block time remaining
#
# Git indicators: +staged ~unstaged-modified -unstaged-deleted •untracked
# Colors: green <40%, yellow 40-79%, red ≥80%
# Block colors: green >2h, yellow 30m-2h, red <30m

# Read JSON input from stdin
input=$(cat)

# Extract JSON fields safely using read (avoids eval command injection)
{
    read -r model_name
    read -r cwd
    read -r project_dir
    read -r total_input
    read -r total_output
    read -r current_input
    read -r current_output
    read -r context_size
    read -r exceeds_200k
    read -r duration_ms
    read -r api_duration_ms
    read -r lines_added
    read -r lines_removed
    read -r cache_read
    read -r cache_create
    read -r version
    read -r output_style
} < <(echo "$input" | jq -r '
    .model.display_name // .model.id // "unknown",
    .workspace.current_dir // .cwd // ".",
    .workspace.project_dir // .cwd // ".",
    .context_window.total_input_tokens // 0,
    .context_window.total_output_tokens // 0,
    .context_window.current_usage.input_tokens // 0,
    .context_window.current_usage.output_tokens // 0,
    .context_window.context_window_size // 200000,
    .exceeds_200k_tokens // false,
    .cost.total_duration_ms // 0,
    .cost.total_api_duration_ms // 0,
    .cost.total_lines_added // 0,
    .cost.total_lines_removed // 0,
    .context_window.current_usage.cache_read_input_tokens // 0,
    .context_window.current_usage.cache_creation_input_tokens // 0,
    .version // "",
    .output_style.name // ""
')

# Calculate context usage - only INPUT tokens count against context window
# Formula: input_tokens + cache_creation + cache_read (output tokens don't count)
context_used=$((current_input + cache_create + cache_read))
total_tokens=$((total_input + total_output))

# Calculate percentage using input tokens only (accurate context window %)
if [[ "$context_size" -gt 0 ]]; then
    usage_pct=$((context_used * 100 / context_size))
else
    usage_pct=0
fi

# Cap at 100%
[[ "$usage_pct" -gt 100 ]] && usage_pct=100

# API latency percentage
api_pct_display=""
if [[ "$duration_ms" -gt 0 && "$api_duration_ms" -gt 0 ]]; then
    api_pct=$((api_duration_ms * 100 / duration_ms))
    [[ "$api_pct" -gt 100 ]] && api_pct=100
    if [[ "$api_pct" -gt 0 ]]; then
        api_pct_display="API:${api_pct}%"
    fi
fi

# 200K warning
warning_display=""
if [[ "$exceeds_200k" == "true" ]]; then
    warning_display="⚠️"
fi

# Format duration (show as Xm or Xh Ym)
duration_display=""
if [[ "$duration_ms" -gt 0 ]]; then
    duration_s=$((duration_ms / 1000))
    if [[ "$duration_s" -ge 3600 ]]; then
        hours=$((duration_s / 3600))
        mins=$(((duration_s % 3600) / 60))
        duration_display="${hours}h${mins}m"
    elif [[ "$duration_s" -ge 60 ]]; then
        mins=$((duration_s / 60))
        duration_display="${mins}m"
    else
        duration_display="${duration_s}s"
    fi
fi

# 5-hour block timer
block_state_file="/tmp/claude_block_start"
now=$(date +%s)
block_duration=$((5 * 60 * 60))  # 5 hours in seconds

# Read or initialize block start time
if [[ -f "$block_state_file" ]]; then
    block_start=$(cat "$block_state_file")
    elapsed=$((now - block_start))
    if [[ "$elapsed" -ge "$block_duration" ]]; then
        # Block expired, start new one
        block_start=$now
        echo "$block_start" > "$block_state_file"
    fi
else
    block_start=$now
    echo "$block_start" > "$block_state_file"
fi

# Calculate time remaining
elapsed=$((now - block_start))
remaining=$((block_duration - elapsed))
remaining_hrs=$((remaining / 3600))
remaining_mins=$(((remaining % 3600) / 60))

# Format block timer display
if [[ "$remaining_hrs" -gt 0 ]]; then
    block_display="⏱${remaining_hrs}h${remaining_mins}m"
else
    block_display="⏱${remaining_mins}m"
fi

# Block timer color (green >2h, yellow 30m-2h, red <30m)
if [[ "$remaining" -gt 7200 ]]; then
    block_color="\033[2;32m"  # dim green
elif [[ "$remaining" -gt 1800 ]]; then
    block_color="\033[2;33m"  # dim yellow
else
    block_color="\033[2;31m"  # dim red
fi

# Cache % of context (how much context is from cache)
cache_display=""
if [[ "$context_used" -gt 0 && "$cache_read" -gt 1000 ]]; then
    cache_pct=$((cache_read * 100 / context_used))
    cache_display="⚡${cache_pct}%"
fi

# Format lines changed (+N/-M)
lines_display=""
if [[ "$lines_added" -gt 0 || "$lines_removed" -gt 0 ]]; then
    lines_display="+${lines_added}/-${lines_removed}"
fi

# Shell prompt info - show relative path if in project subdirectory
if [[ "$cwd" == "$project_dir" ]]; then
    # At project root
    path="${cwd/#$HOME/~}"
elif [[ "$cwd" == "$project_dir"/* ]]; then
    # In subdirectory - show relative path
    path="${cwd#$project_dir/}"
else
    # Different directory
    path="${cwd/#$HOME/~}"
fi

# Git information (single git call)
git_info=""
git_output=$(git -C "$cwd" --no-optional-locks status -sb 2>/dev/null) || true
if [[ -n "$git_output" ]]; then
    # First line: ## branch...tracking info
    branch=$(echo "$git_output" | head -1 | sed 's/^## //; s/\.\.\..*$//')
    # Remaining lines: file status
    git_files=$(echo "$git_output" | tail -n +2)

    if [[ -n "$git_files" ]]; then
        # Git status format: XY where X=staged, Y=unstaged
        # Staged changes: first char is A/M/D/R/C (not space or ?)
        staged=$(echo "$git_files" | grep -cE "^[AMDRC]" || true)
        # Unstaged modifications: second char is M
        modified=$(echo "$git_files" | grep -c "^.M" || true)
        # Unstaged deletions: second char is D
        deleted=$(echo "$git_files" | grep -c "^.D" || true)
        # Untracked files
        untracked=$(echo "$git_files" | grep -c "^??" || true)

        status_indicators=""
        [[ "$staged" -gt 0 ]] && status_indicators="${status_indicators}+${staged}"
        [[ "$modified" -gt 0 ]] && status_indicators="${status_indicators}~${modified}"
        [[ "$deleted" -gt 0 ]] && status_indicators="${status_indicators}-${deleted}"
        [[ "$untracked" -gt 0 ]] && status_indicators="${status_indicators}•${untracked}"

        git_info=" | git:${branch}[${status_indicators}]"
    else
        git_info=" | git:${branch}"
    fi
fi

# Context usage color indicator
if [[ "$usage_pct" -ge 80 ]]; then
    ctx_color="\033[2;31m"  # dim red
elif [[ "$usage_pct" -ge 40 ]]; then
    ctx_color="\033[2;33m"  # dim yellow
else
    ctx_color="\033[2;32m"  # dim green
fi

# Build sections by logical grouping

# 2. Path section
path_section="\033[2;34m${path}\033[0m"

# 3. Git section (branch + status)
git_section=""
if [[ -n "$git_info" ]]; then
    git_section="\033[2;35m${git_info# | git:}\033[0m | "
fi

# 4. Model section
model_section="\033[2;36m${model_name}\033[0m"

# 6. Context section (% + cache + warning)
context_section="${ctx_color}${usage_pct}%"
[[ -n "$cache_display" ]] && context_section="${context_section} ${cache_display}"
context_section="${context_section}\033[0m"
[[ -n "$warning_display" ]] && context_section="${context_section} \033[1;31m${warning_display}\033[0m"

# 8. Token section (input↓ output↑)
token_section=""
if [[ "$total_tokens" -gt 0 ]]; then
    # Format input tokens
    if [[ "$total_input" -ge 1000000 ]]; then
        in_display="$((total_input / 1000000))M"
    elif [[ "$total_input" -ge 1000 ]]; then
        in_display="$((total_input / 1000))K"
    else
        in_display="${total_input}"
    fi

    # Format output tokens
    if [[ "$total_output" -ge 1000000 ]]; then
        out_display="$((total_output / 1000000))M"
    elif [[ "$total_output" -ge 1000 ]]; then
        out_display="$((total_output / 1000))K"
    else
        out_display="${total_output}"
    fi

    # Calculate tokens per minute (if session > 1 min)
    tok_rate_display=""
    if [[ "$duration_ms" -gt 60000 ]]; then
        tok_per_min=$(awk -v tt="$total_tokens" -v dm="$duration_ms" 'BEGIN {printf "%.0f", (tt / dm) * 60000}')
        if [[ "$tok_per_min" -ge 1000 ]]; then
            tok_rate_display=" $((tok_per_min / 1000))K/m"
        elif [[ "$tok_per_min" -gt 0 ]]; then
            tok_rate_display=" ${tok_per_min}/m"
        fi
    fi

    token_section=" | \033[2;33m${in_display}↓ ${out_display}↑${tok_rate_display}\033[0m"
fi

# 9. Time section (duration + API%)
time_section=""
if [[ -n "$duration_display" && -n "$api_pct_display" ]]; then
    time_section=" | \033[2;37m${duration_display} ${api_pct_display}\033[0m"
elif [[ -n "$duration_display" ]]; then
    time_section=" | \033[2;37m${duration_display}\033[0m"
fi

# 5. Style section (output style)
style_section=""
[[ -n "$output_style" ]] && style_section=" | \033[2;90m${output_style}\033[0m"

# 7. Output section (lines changed)
output_section=""
[[ -n "$lines_display" ]] && output_section=" | \033[2;32m${lines_display}\033[0m"

# 10. Block timer section
block_section=" | ${block_color}${block_display}\033[0m"

# Build the complete status line
# Format: v2.0.76 | path | branch[status] | Model | terse | 45% ⚡99% ⚠️ | +N/-M | 79K↓ 68K↑ | 10m API:15%
version_prefix=""
[[ -n "$version" ]] && version_prefix="\033[2;90mv${version}\033[0m | "
echo -e "${version_prefix}${path_section} | ${git_section}${model_section}${style_section} | ${context_section}${output_section}${token_section}${time_section}${block_section}"
