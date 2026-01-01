"""
Metrics utilities - Token estimation and content size measurement.

Consolidates token estimation from tool_analytics.py and context_monitor.py.
"""
import json
from typing import Any

from config import Thresholds

# Character-based estimation (fast, approximate)
CHARS_PER_TOKEN = Thresholds.CHARS_PER_TOKEN

# Lazy-loaded tiktoken encoder for accurate counting
_encoder = None


def _get_encoder():
    """Lazy-load tiktoken encoder."""
    global _encoder
    if _encoder is None:
        try:
            import tiktoken
            _encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _encoder = False  # Mark as unavailable
    return _encoder if _encoder else None


def estimate_tokens(content: Any, accurate: bool = False) -> int:
    """
    Estimate token count from content.

    Args:
        content: String, dict, or list to estimate
        accurate: If True, use tiktoken (slower but accurate).
                  If False, use char/token ratio (fast approximation).

    Returns:
        Estimated token count
    """
    if content is None:
        return 0

    # Convert to string first
    if isinstance(content, str):
        text = content
    elif isinstance(content, dict):
        text = json.dumps(content)
    elif isinstance(content, list):
        return sum(estimate_tokens(item, accurate) for item in content)
    else:
        text = str(content)

    if not text:
        return 0

    if accurate:
        encoder = _get_encoder()
        if encoder:
            return len(encoder.encode(text))

    # Fast approximation
    return len(text) // CHARS_PER_TOKEN


def get_content_size(content: Any) -> int:
    """
    Get size of content in characters.

    Args:
        content: String, dict, or list to measure

    Returns:
        Size in characters
    """
    if content is None:
        return 0

    if isinstance(content, str):
        return len(content)
    elif isinstance(content, dict):
        return len(json.dumps(content))
    elif isinstance(content, list):
        return sum(get_content_size(item) for item in content)
    else:
        return len(str(content))


def count_tokens_accurate(text: str) -> int:
    """
    Accurate token count using tiktoken.

    Falls back to character estimation if tiktoken unavailable.
    """
    return estimate_tokens(text, accurate=True)
