#!/usr/bin/env bash
# Claude Code Status Line (v2.0.70+)
#
# Format: branch[•N] | path | Model | [████░░] 45% ⚡85% ⚠️ | 10m API:15% | +50/-10 | 120K↓ 50K↑ 5K/m
#
# Sections (logically grouped):
#   1. Git:     branch[~2+1-1•3] - branch name + status indicators
#   2. Path:    ~/project or subdir/ if in project subdirectory
#   3. Model:   Opus 4.5, Sonnet, Haiku
#   4. Context: [████░░░░] 45% ⚡85% ⚠️ - progress bar, %, cache hit, 200K warning
#   5. Time:    10m API:15% - duration + API latency %
#   6. Output:  +50/-10 - lines added/removed
#   7. Tokens:  120K↓ 50K↑ 5K/m - input↓, output↑, rate per minute
#
# Git indicators: ~modified +staged -deleted •untracked
# Colors: green <40%, yellow 40-79%, red ≥80%

# Read JSON input from stdin
input=$(cat)

# Extract JSON fields (single jq call for efficiency)
eval "$(echo "$input" | jq -r '
  @sh "model_name=\(.model.display_name // .model.id)",
  @sh "cwd=\(.workspace.current_dir // .cwd)",
  @sh "project_dir=\(.workspace.project_dir // .cwd)",
  @sh "total_input=\(.context_window.total_input_tokens // 0)",
  @sh "total_output=\(.context_window.total_output_tokens // 0)",
  @sh "current_input=\(.context_window.current_usage.input_tokens // 0)",
  @sh "current_output=\(.context_window.current_usage.output_tokens // 0)",
  @sh "context_size=\(.context_window.context_window_size // 200000)",
  @sh "exceeds_200k=\(.exceeds_200k_tokens // false)",
  @sh "json_session_id=\(.session_id // "unknown")",
  @sh "total_cost=\(.cost.total_cost_usd // 0)",
  @sh "duration_ms=\(.cost.total_duration_ms // 0)",
  @sh "api_duration_ms=\(.cost.total_api_duration_ms // 0)",
  @sh "lines_added=\(.cost.total_lines_added // 0)",
  @sh "lines_removed=\(.cost.total_lines_removed // 0)",
  @sh "cache_read=\(.context_window.current_usage.cache_read_input_tokens // 0)",
  @sh "cache_create=\(.context_window.current_usage.cache_creation_input_tokens // 0)"
' | tr '\n' ' ')"

# Calculate context usage - only INPUT tokens count against context window
# Formula: input_tokens + cache_creation + cache_read (output tokens don't count)
context_used=$((current_input + cache_create + cache_read))
total_tokens=$((total_input + total_output))

# --- Delta tracking for cost changes ---
state_dir="/tmp/claude_statusline"
mkdir -p "$state_dir" 2>/dev/null
state_file="${state_dir}/${json_session_id}"

# Read previous state for cost delta
if [[ -f "$state_file" ]]; then
    read -r last_total last_cost < "$state_file"
    last_cost=${last_cost:-0}
else
    last_total=0
    last_cost=0
fi

# Calculate token delta since last update (for +5K indicator)
delta=$((total_tokens - last_total))

# Calculate cost delta (using awk for floating point)
cost_delta=$(awk "BEGIN {printf \"%.4f\", $total_cost - $last_cost}")

# Save state for next call
echo "$total_tokens $total_cost" > "$state_file"

# Calculate percentage using input tokens only (accurate context window %)
if [[ "$context_size" -gt 0 ]]; then
    usage_pct=$((context_used * 100 / context_size))
else
    usage_pct=0
fi

# Cap at 100%
[[ "$usage_pct" -gt 100 ]] && usage_pct=100

# Progress bar function (8 chars wide)
make_progress_bar() {
    local pct=$1
    local width=8
    local filled=$((pct * width / 100))
    local empty=$((width - filled))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    echo "$bar"
}

# Build progress bar with color
progress_bar=$(make_progress_bar "$usage_pct")

# Burn rate calculation ($/hr)
burn_rate_display=""
if [[ "$duration_ms" -gt 60000 ]]; then  # Only show after 1 minute
    # cost per hour = (cost / duration_ms) * 3600000
    burn_rate=$(awk "BEGIN {printf \"%.2f\", ($total_cost / $duration_ms) * 3600000}")
    if [[ $(awk "BEGIN {print ($burn_rate > 0.01) ? 1 : 0}") == "1" ]]; then
        burn_rate_display="\$${burn_rate}/hr"
    fi
fi

# API latency percentage
api_pct_display=""
if [[ "$duration_ms" -gt 0 && "$api_duration_ms" -gt 0 ]]; then
    api_pct=$((api_duration_ms * 100 / duration_ms))
    if [[ "$api_pct" -gt 0 ]]; then
        api_pct_display="API:${api_pct}%"
    fi
fi

# 200K warning
warning_display=""
if [[ "$exceeds_200k" == "true" ]]; then
    warning_display="⚠️"
fi

# Format cost display (show delta if > $0.001, otherwise show total)
cost_display=""
is_cost_positive=$(awk "BEGIN {print ($cost_delta > 0.001) ? 1 : 0}")
if [[ "$is_cost_positive" == "1" ]]; then
    # Show cost delta for last operation
    cost_display=$(awk "BEGIN {printf \"+\$%.2f\", $cost_delta}")
elif [[ $(awk "BEGIN {print ($total_cost > 0.01) ? 1 : 0}") == "1" ]]; then
    # Show total session cost if no recent delta
    cost_display=$(awk "BEGIN {printf \"\$%.2f\", $total_cost}")
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

# Cache hit percentage (if caching is active)
cache_display=""
total_cache=$((cache_read + cache_create))
if [[ "$total_cache" -gt 1000 ]]; then
    if [[ "$cache_create" -gt 0 ]]; then
        cache_pct=$((cache_read * 100 / (cache_read + cache_create)))
    else
        cache_pct=100
    fi
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

# Git information
git_info=""
if [[ -d "$cwd/.git" ]] || git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)

    if [[ -n "$branch" ]]; then
        git_status=$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)

        if [[ -n "$git_status" ]]; then
            modified=$(echo "$git_status" | grep -c "^ M" || true)
            added=$(echo "$git_status" | grep -c "^A" || true)
            deleted=$(echo "$git_status" | grep -c "^ D" || true)
            untracked=$(echo "$git_status" | grep -c "^??" || true)
        else
            modified=0 added=0 deleted=0 untracked=0
        fi

        status_indicators=""
        [[ "$modified" -gt 0 ]] && status_indicators="${status_indicators}~${modified}"
        [[ "$added" -gt 0 ]] && status_indicators="${status_indicators}+${added}"
        [[ "$deleted" -gt 0 ]] && status_indicators="${status_indicators}-${deleted}"
        [[ "$untracked" -gt 0 ]] && status_indicators="${status_indicators}•${untracked}"

        if [[ -z "$git_status" ]]; then
            git_info=" | git:${branch}"
        else
            git_info=" | git:${branch}[${status_indicators}]"
        fi
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

# 1. Git section (branch + status) - moved to front
git_section=""
if [[ -n "$git_info" ]]; then
    # Extract just "branch[status]" without " | git:" prefix
    git_section="\033[2;35m${git_info# | git:}\033[0m | "
fi

# 2. Path section
path_section="\033[2;34m${path}\033[0m"

# 3. Model section
model_section="\033[2;36m${model_name}\033[0m"

# 4. Context section (bar + % + cache + warning - all together)
context_section="${ctx_color}[${progress_bar}] ${usage_pct}%"
[[ -n "$cache_display" ]] && context_section="${context_section} ${cache_display}"
context_section="${context_section}\033[0m"
[[ -n "$warning_display" ]] && context_section="${context_section} \033[1;31m${warning_display}\033[0m"

# 5. Token section (input↓ output↑ + burn rate)
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
        tok_per_min=$(awk "BEGIN {printf \"%.0f\", ($total_tokens / $duration_ms) * 60000}")
        if [[ "$tok_per_min" -ge 1000 ]]; then
            tok_rate_display=" $((tok_per_min / 1000))K/m"
        elif [[ "$tok_per_min" -gt 0 ]]; then
            tok_rate_display=" ${tok_per_min}/m"
        fi
    fi

    token_section=" | \033[2;33m${in_display}↓ ${out_display}↑${tok_rate_display}\033[0m"
fi

# 6. Time section (duration + API%)
time_section=""
if [[ -n "$duration_display" && -n "$api_pct_display" ]]; then
    time_section=" | \033[2;37m${duration_display} ${api_pct_display}\033[0m"
elif [[ -n "$duration_display" ]]; then
    time_section=" | \033[2;37m${duration_display}\033[0m"
fi

# 7. Output section (lines changed)
output_section=""
[[ -n "$lines_display" ]] && output_section=" | \033[2;32m${lines_display}\033[0m"

# Build the complete status line
# Format: branch[status] | path | Model | [████░░] 45% ⚡cache ⚠️ | duration API:% | +N/-M | 150K 5K/m
echo -e "${git_section}${path_section} | ${model_section} | ${context_section}${time_section}${output_section}${token_section}"
