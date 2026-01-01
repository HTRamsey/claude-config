"""
Path utilities - Centralized path handling for hooks.

Provides consistent path normalization, expansion, and pattern matching
across all hooks.
"""

from pathlib import Path
import os


def normalize_path(path: str) -> str:
    """Normalize path to absolute resolved form.

    Converts relative paths to absolute and resolves symlinks.
    If path resolution fails, returns the original path.

    Args:
        path: Path string to normalize

    Returns:
        Absolute resolved path, or original path on error
    """
    try:
        return str(Path(path).resolve())
    except (OSError, ValueError):
        return path


def expand_path(path: str) -> str:
    """Expand ~ and environment variables.

    Replaces ~ with user home directory and expands ${VAR} style
    environment variables.

    Args:
        path: Path string with ~ or ${VAR} references

    Returns:
        Expanded path string
    """
    return os.path.expandvars(os.path.expanduser(path))


def relative_to(path: str, base: str) -> str:
    """Make path relative to base if possible.

    Attempts to express path as relative to base directory.
    If paths are on different drives or resolution fails, returns
    the original path.

    Args:
        path: Path to make relative
        base: Base directory path

    Returns:
        Relative path if possible, otherwise original path
    """
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path


def matches_pattern(path: str, pattern: str) -> bool:
    """Check if path matches glob pattern using pathlib.

    Uses pathlib.Path.match() for consistent cross-platform matching.

    Args:
        path: Path string to check
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")

    Returns:
        True if path matches pattern, False otherwise
    """
    return Path(path).match(pattern)
