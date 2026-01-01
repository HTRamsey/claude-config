"""
Safe File Operations - Graceful error handling for file I/O.

Provides atomic wrappers around file operations that handle OSError,
PermissionError, and other common file system errors gracefully.

All functions return sensible defaults on error (empty string, 0, None, False)
instead of raising exceptions, making them suitable for non-critical operations
where missing data is acceptable.

Usage:
    from hook_utils.file_ops import safe_read_file, safe_mtime, safe_exists

    content = safe_read_file("/path/to/file.txt")  # Empty string if error
    mtime = safe_mtime("/path/to/file.txt")        # 0.0 if error
    exists = safe_exists("/path/to/file.txt")      # False if error
"""

import os
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def safe_read_file(path: PathLike, default: str = "") -> str:
    """
    Read file contents safely, return default on any error.

    Handles:
    - FileNotFoundError
    - PermissionError
    - IsADirectoryError
    - UnicodeDecodeError
    - OSError

    Args:
        path: File path (str or Path)
        default: Return value if read fails

    Returns:
        File contents as string, or default on error
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, PermissionError, IsADirectoryError,
            UnicodeDecodeError, OSError):
        return default


def safe_read_bytes(path: PathLike, default: bytes = b"") -> bytes:
    """
    Read file as bytes safely, return default on any error.

    Handles:
    - FileNotFoundError
    - PermissionError
    - IsADirectoryError
    - OSError

    Args:
        path: File path (str or Path)
        default: Return value if read fails

    Returns:
        File contents as bytes, or default on error
    """
    try:
        with open(path, 'rb') as f:
            return f.read()
    except (FileNotFoundError, PermissionError, IsADirectoryError, OSError):
        return default


def safe_stat(path: PathLike) -> os.stat_result | None:
    """
    Get file stats safely, return None on error.

    Handles:
    - FileNotFoundError
    - PermissionError
    - OSError

    Args:
        path: File path (str or Path)

    Returns:
        os.stat_result object, or None on error

    Example:
        stat = safe_stat("/path/to/file.txt")
        if stat:
            print(f"Size: {stat.st_size}, Mode: {stat.st_mode}")
    """
    try:
        return os.stat(path)
    except (FileNotFoundError, PermissionError, OSError):
        return None


def safe_mtime(path: PathLike, default: float = 0.0) -> float:
    """
    Get file modification time safely, return default on error.

    Handles:
    - FileNotFoundError
    - PermissionError
    - OSError

    Args:
        path: File path (str or Path)
        default: Return value if stat fails (typically 0.0)

    Returns:
        Modification time as float (seconds since epoch), or default on error

    Example:
        mtime = safe_mtime("/path/to/file.txt")
        if mtime > some_time:
            print("File was modified after some_time")
    """
    try:
        return os.path.getmtime(path)
    except (FileNotFoundError, PermissionError, OSError):
        return default


def safe_size(path: PathLike, default: int = 0) -> int:
    """
    Get file size in bytes safely, return default on error.

    Handles:
    - FileNotFoundError
    - PermissionError
    - OSError

    Args:
        path: File path (str or Path)
        default: Return value if stat fails (typically 0)

    Returns:
        File size in bytes, or default on error

    Example:
        size = safe_size("/path/to/file.txt")
        if size > 1024 * 1024:  # > 1MB
            print("Large file detected")
    """
    try:
        return os.path.getsize(path)
    except (FileNotFoundError, PermissionError, OSError):
        return default


def safe_exists(path: PathLike) -> bool:
    """
    Check if path exists safely, return False on error.

    Handles:
    - OSError
    - PermissionError

    Note: Unlike os.path.exists(), this returns False for permission errors
    (rather than attempting to raise), which is consistent with the module's
    philosophy that missing data is acceptable in non-critical operations.

    Args:
        path: File path (str or Path)

    Returns:
        True if path exists and is accessible, False otherwise

    Example:
        if safe_exists("/path/to/file.txt"):
            content = safe_read_file("/path/to/file.txt")
    """
    try:
        return os.path.exists(path)
    except (OSError, PermissionError):
        return False


__all__ = [
    "safe_read_file",
    "safe_read_bytes",
    "safe_stat",
    "safe_mtime",
    "safe_size",
    "safe_exists",
]
