#!/usr/bin/env python3
"""
Claude Code usage statistics from local JSONL session files.

Parses ~/.claude/projects/*/*.jsonl to extract token usage.
Replaces ccusage without the cost calculation.

Usage:
    usage-stats.py [daily|weekly|monthly|session|today]
    usage-stats.py --update-cache  # Update cache for statusline
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude/projects"
CACHE_FILE = Path.home() / ".claude/data/usage-cache.json"


def parse_jsonl_usage(filepath: Path) -> list[dict]:
    """Extract usage records from a JSONL session file."""
    records = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Look for message records with usage data
                    if 'message' in data and isinstance(data['message'], dict):
                        msg = data['message']
                        if 'usage' in msg:
                            usage = msg['usage']
                            timestamp = data.get('timestamp', '')
                            model = msg.get('model', 'unknown')
                            records.append({
                                'timestamp': timestamp,
                                'model': model,
                                'input_tokens': usage.get('input_tokens', 0),
                                'output_tokens': usage.get('output_tokens', 0),
                                'cache_creation': usage.get('cache_creation_input_tokens', 0),
                                'cache_read': usage.get('cache_read_input_tokens', 0),
                            })
                except json.JSONDecodeError:
                    continue
    except (IOError, OSError):
        pass
    return records


def get_all_usage() -> list[dict]:
    """Get all usage records from all project JSONL files."""
    all_records = []
    for jsonl_file in PROJECTS_DIR.rglob("*.jsonl"):
        all_records.extend(parse_jsonl_usage(jsonl_file))
    return all_records


def aggregate_by_period(records: list[dict], period: str) -> dict:
    """Aggregate records by time period."""
    aggregated = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation': 0,
        'cache_read': 0,
        'requests': 0,
        'models': set(),
    })

    for r in records:
        ts = r.get('timestamp', '')
        if not ts:
            continue

        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            continue

        if period == 'daily':
            key = dt.strftime('%Y-%m-%d')
        elif period == 'weekly':
            key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        elif period == 'monthly':
            key = dt.strftime('%Y-%m')
        elif period == 'session':
            key = ts[:19]  # Use timestamp as session key (rough)
        else:
            key = 'total'

        agg = aggregated[key]
        agg['input_tokens'] += r['input_tokens']
        agg['output_tokens'] += r['output_tokens']
        agg['cache_creation'] += r['cache_creation']
        agg['cache_read'] += r['cache_read']
        agg['requests'] += 1
        agg['models'].add(r.get('model', 'unknown'))

    # Convert sets to lists for JSON serialization
    for key in aggregated:
        aggregated[key]['models'] = list(aggregated[key]['models'])

    return dict(aggregated)


def format_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_today_usage(records: list[dict]) -> dict:
    """Get today's usage totals."""
    today = datetime.now().strftime('%Y-%m-%d')
    totals = {
        'date': today,
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation': 0,
        'cache_read': 0,
        'requests': 0,
    }

    for r in records:
        ts = r.get('timestamp', '')
        if ts.startswith(today):
            totals['input_tokens'] += r['input_tokens']
            totals['output_tokens'] += r['output_tokens']
            totals['cache_creation'] += r['cache_creation']
            totals['cache_read'] += r['cache_read']
            totals['requests'] += 1

    totals['total_tokens'] = totals['input_tokens'] + totals['output_tokens']
    return totals


def update_cache():
    """Update the cache file for statusline consumption."""
    records = get_all_usage()
    today = get_today_usage(records)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump({
            'today': today,
            'updated': datetime.now().isoformat(),
        }, f, indent=2)

    print(f"Cache updated: {format_tokens(today['total_tokens'])} tokens today")


def print_report(period: str):
    """Print usage report for the given period."""
    records = get_all_usage()

    if period == 'today':
        today = get_today_usage(records)
        print(f"\n  Today's Usage ({today['date']})")
        print(f"  {'─' * 40}")
        print(f"  Input:    {format_tokens(today['input_tokens']):>10}")
        print(f"  Output:   {format_tokens(today['output_tokens']):>10}")
        print(f"  Cache ↻:  {format_tokens(today['cache_read']):>10}")
        print(f"  Cache +:  {format_tokens(today['cache_creation']):>10}")
        print(f"  {'─' * 40}")
        print(f"  Total:    {format_tokens(today['total_tokens']):>10}")
        print(f"  Requests: {today['requests']:>10}")
        return

    aggregated = aggregate_by_period(records, period)

    if not aggregated:
        print("No usage data found.")
        return

    # Sort by key (date)
    sorted_keys = sorted(aggregated.keys(), reverse=True)

    # Print header
    print(f"\n  {'Period':<12} {'Input':>10} {'Output':>10} {'Cache ↻':>10} {'Total':>12}")
    print(f"  {'─' * 56}")

    for key in sorted_keys[:20]:  # Show last 20
        data = aggregated[key]
        total = data['input_tokens'] + data['output_tokens']
        print(f"  {key:<12} {format_tokens(data['input_tokens']):>10} "
              f"{format_tokens(data['output_tokens']):>10} "
              f"{format_tokens(data['cache_read']):>10} "
              f"{format_tokens(total):>12}")

    # Print totals
    total_in = sum(d['input_tokens'] for d in aggregated.values())
    total_out = sum(d['output_tokens'] for d in aggregated.values())
    total_cache = sum(d['cache_read'] for d in aggregated.values())
    grand_total = total_in + total_out

    print(f"  {'─' * 56}")
    print(f"  {'Total':<12} {format_tokens(total_in):>10} "
          f"{format_tokens(total_out):>10} "
          f"{format_tokens(total_cache):>10} "
          f"{format_tokens(grand_total):>12}")


def main():
    if len(sys.argv) < 2:
        period = 'daily'
    elif sys.argv[1] == '--update-cache':
        update_cache()
        return
    else:
        period = sys.argv[1]

    if period not in ('daily', 'weekly', 'monthly', 'session', 'today'):
        print(f"Unknown period: {period}")
        print("Usage: usage-stats.py [daily|weekly|monthly|session|today|--update-cache]")
        sys.exit(1)

    print_report(period)


if __name__ == '__main__':
    main()
