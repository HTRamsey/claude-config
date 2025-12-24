#!/usr/bin/env bash
# evaluate-subscription.sh - Analyze Claude usage and recommend subscription plan
#
# Usage:
#   evaluate-subscription.sh              # Analyze recent usage
#   evaluate-subscription.sh --detailed   # Show detailed breakdown
#   evaluate-subscription.sh --history    # Show usage history
#
# Compares your API usage costs against subscription plans to recommend
# the most cost-effective option.

set -e

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Subscription plans (as of 2025)
PLAN_MAX_100=100
PLAN_MAX_200=200

# History file location (Claude Code stores session data here)
CLAUDE_DIR="$HOME/.claude"
HISTORY_FILE="$CLAUDE_DIR/history.jsonl"
PROJECTS_DIR="$CLAUDE_DIR/projects"

print_header() {
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}       Claude Subscription Evaluation Tool${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    echo -e "${BOLD}${BLUE}── $1 ──${NC}"
}

estimate_monthly_cost() {
    # Try to estimate based on available data
    local total_cost=0
    local session_count=0
    local days_analyzed=0

    # Check for session transcripts
    if [[ -d "$PROJECTS_DIR" ]]; then
        # Count sessions from last 30 days
        local recent_sessions=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -30 2>/dev/null | wc -l)
        session_count=$recent_sessions

        # Estimate based on typical session cost ($0.50-$2.00 average)
        # Conservative estimate: $1 per session
        total_cost=$(echo "$session_count * 1.0" | bc 2>/dev/null || echo "$session_count")
        days_analyzed=30
    fi

    echo "$total_cost|$session_count|$days_analyzed"
}

analyze_usage_patterns() {
    print_section "Usage Pattern Analysis"

    local sessions_30d=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -30 2>/dev/null | wc -l)
    local sessions_7d=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -7 2>/dev/null | wc -l)
    local sessions_1d=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -1 2>/dev/null | wc -l)

    echo "Sessions (last 24h):  $sessions_1d"
    echo "Sessions (last 7d):   $sessions_7d"
    echo "Sessions (last 30d):  $sessions_30d"

    # Calculate daily average
    if [[ $sessions_30d -gt 0 ]]; then
        local daily_avg=$(echo "scale=1; $sessions_30d / 30" | bc)
        echo "Daily average:        $daily_avg sessions/day"
    fi
    echo ""
}

calculate_transcript_sizes() {
    print_section "Context Usage Analysis"

    # Use du for faster total size calculation
    local total_size=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -30 -exec stat -c%s {} \; 2>/dev/null | awk '{sum+=$1} END {print sum+0}')
    local file_count=$(find "$PROJECTS_DIR" -name "*.jsonl" -mtime -30 2>/dev/null | wc -l)

    if [[ $file_count -gt 0 ]] && [[ $total_size -gt 0 ]]; then
        local avg_size=$((total_size / file_count))
        local total_mb=$((total_size / 1048576))
        local avg_kb=$((avg_size / 1024))

        echo "Total transcript data: ${total_mb}MB"
        echo "Average session size:  ${avg_kb}KB"
        echo "Estimated tokens/session: ~$((avg_size / 4))"

        # Rough cost estimate per session
        local tokens_per_session=$((avg_size / 4))
        # Sonnet: $3/1M input, $15/1M output - estimate ~$0.00002 per token average
        local cost_cents=$((tokens_per_session * 2 / 1000))  # cents
        echo "Est. cost/session:     \$0.$cost_cents"
    else
        echo "No recent session data found"
    fi
    echo ""
}

make_recommendation() {
    local monthly_estimate="$1"

    print_section "Subscription Recommendation"

    # Remove decimal for comparison
    local cost_int=${monthly_estimate%.*}
    cost_int=${cost_int:-0}

    echo -e "Estimated monthly spend: ${BOLD}\$${monthly_estimate}${NC}"
    echo ""

    if [[ $cost_int -lt 50 ]]; then
        echo -e "${GREEN}✓ RECOMMENDATION: Stay on API (Pay-as-you-go)${NC}"
        echo ""
        echo "  Your estimated usage is below \$50/month."
        echo "  Pay-as-you-go is most cost-effective for you."
        echo ""
        echo "  Potential savings: None needed"

    elif [[ $cost_int -lt 100 ]]; then
        echo -e "${YELLOW}◐ RECOMMENDATION: Consider Claude Max \$100${NC}"
        echo ""
        echo "  Your usage is approaching \$100/month."
        echo "  Consider switching if usage increases."
        echo ""
        local savings=$((cost_int - 0))
        echo "  Current API cost:    ~\$${monthly_estimate}/month"
        echo "  Claude Max \$100:     \$100/month (flat)"
        echo "  Break-even point:    \$100/month usage"

    elif [[ $cost_int -lt 200 ]]; then
        echo -e "${GREEN}✓ RECOMMENDATION: Claude Max \$100${NC}"
        echo ""
        echo "  Your usage exceeds \$100/month."
        echo "  Claude Max \$100 will save you money."
        echo ""
        local savings=$((cost_int - 100))
        echo "  Current API cost:    ~\$${monthly_estimate}/month"
        echo "  Claude Max \$100:     \$100/month (flat)"
        echo -e "  ${GREEN}Potential savings:   ~\$${savings}/month${NC}"

    else
        echo -e "${GREEN}✓ RECOMMENDATION: Claude Max \$200${NC}"
        echo ""
        echo "  Your usage significantly exceeds \$200/month."
        echo "  Claude Max \$200 offers the best value."
        echo ""
        local savings=$((cost_int - 200))
        echo "  Current API cost:    ~\$${monthly_estimate}/month"
        echo "  Claude Max \$200:     \$200/month (flat)"
        echo -e "  ${GREEN}Potential savings:   ~\$${savings}/month${NC}"
    fi
    echo ""
}

show_plan_comparison() {
    print_section "Plan Comparison"

    echo "┌─────────────────────┬──────────────┬─────────────────────────┐"
    echo "│ Plan                │ Cost         │ Best For                │"
    echo "├─────────────────────┼──────────────┼─────────────────────────┤"
    echo "│ API Pay-as-you-go   │ Variable     │ <\$100/month usage       │"
    echo "│ Claude Max \$100     │ \$100/month   │ \$100-200/month usage    │"
    echo "│ Claude Max \$200     │ \$200/month   │ >\$200/month usage       │"
    echo "└─────────────────────┴──────────────┴─────────────────────────┘"
    echo ""
    echo "Note: Claude Max plans include unlimited Claude Code usage."
    echo "Check https://www.anthropic.com/pricing for current pricing."
    echo ""
}

show_cost_tracking_tips() {
    print_section "Cost Tracking Tips"

    echo "1. Run /cost in Claude Code to see current session spending"
    echo "2. Check Anthropic Console for detailed usage history"
    echo "3. Set workspace spend limits for team usage"
    echo "4. Use model selection (claude-model.sh) to optimize costs"
    echo "5. Re-run this tool monthly to track trends"
    echo ""
}

# Main execution
print_header

# Parse arguments
DETAILED=false
HISTORY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --detailed|-d)
            DETAILED=true
            shift
            ;;
        --history|-h)
            HISTORY=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Run analysis
analyze_usage_patterns

if [[ "$DETAILED" == "true" ]]; then
    calculate_transcript_sizes
fi

# Get cost estimate
IFS='|' read -r monthly_cost sessions days <<< "$(estimate_monthly_cost)"

# Calculate more accurate estimate based on sessions
if [[ $sessions -gt 0 ]]; then
    # Assume average $0.75 per session (conservative for mixed model usage)
    monthly_estimate=$(echo "scale=2; $sessions * 0.75" | bc)
else
    monthly_estimate="0"
fi

make_recommendation "$monthly_estimate"
show_plan_comparison

if [[ "$DETAILED" == "true" ]]; then
    show_cost_tracking_tips
fi

echo -e "${CYAN}Run with --detailed for more analysis${NC}"
