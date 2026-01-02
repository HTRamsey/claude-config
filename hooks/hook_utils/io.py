"""
File I/O utilities with locking and graceful error handling.

Includes:
- File locking (file_lock)
- JSON I/O (safe_load_json, safe_save_json, atomic_write_json)
- Safe file operations (safe_stat, safe_mtime, safe_exists)
- Path utilities (normalize_path, expand_path)
"""
import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from hooks.config import fast_json_loads, fast_json_dumps

PathLike = str | Path


# =============================================================================
# Hashing Utilities
# =============================================================================

def stable_hash(text: str, length: int = 12) -> str:
    """Generate a stable MD5 hash of text, truncated to specified length.

    Used for cache keys, deduplication, and stable identifiers.

    Args:
        text: Text to hash
        length: Length of hash to return (default 12, max 32)

    Returns:
        Lowercase hex string of specified length
    """
    return hashlib.md5(text.encode()).hexdigest()[:length]


# =============================================================================
# JSONL Utilities
# =============================================================================

def iter_jsonl(
    path: PathLike,
    tail: int | None = None,
    skip_errors: bool = True
):
    """Iterate over JSONL file, yielding parsed dict per line.

    Consolidates repeated JSONL parsing pattern across handlers.

    Args:
        path: Path to JSONL file
        tail: If set, only yield last N lines (like tail -n)
        skip_errors: If True (default), skip lines with JSON parse errors.
                     If False, raises JSONDecodeError on invalid lines.

    Yields:
        Parsed dict for each valid line

    Example:
        for entry in iter_jsonl(transcript_path, tail=100):
            if entry.get("type") == "assistant":
                process(entry)
    """
    path = Path(path)
    if not path.exists():
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            if tail is not None:
                # Read all lines and take last N
                lines = f.readlines()
                lines = lines[-tail:] if tail else lines
            else:
                lines = f

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    if not skip_errors:
                        raise
                    # Log first few errors, then suppress
                    from hooks.hook_utils.logging import log_event
                    if line_num <= 3:
                        log_event("iter_jsonl", "parse_error", {
                            "path": str(path),
                            "line": line_num
                        })
    except (OSError, IOError):
        return


def count_jsonl_lines(path: PathLike) -> int:
    """Count valid JSON lines in a JSONL file.

    Args:
        path: Path to JSONL file

    Returns:
        Count of valid JSON lines
    """
    count = 0
    for _ in iter_jsonl(path, skip_errors=True):
        count += 1
    return count


@contextmanager
def file_lock(path_or_handle, timeout: float = 10.0):
    """
    Context manager for exclusive file locking.

    Uses filelock library for path-based locking, fcntl for file handles.

    Usage:
        # With file path
        with file_lock("/path/to/file.json", timeout=10.0):
            # perform atomic operation

        # Legacy: with file handle (fcntl fallback)
        with open(path, 'w') as f:
            with file_lock(f):
                json.dump(data, f)
    """
    if isinstance(path_or_handle, (str, Path)):
        # Use filelock for path-based locking (cross-platform)
        path = Path(path_or_handle)
        lock = FileLock(f"{path}.lock", timeout=timeout)
        try:
            lock.acquire()
            yield
        finally:
            try:
                lock.release()
            except Exception:
                pass
    else:
        # Fallback to fcntl for file handles (Unix only)
        file_handle = path_or_handle
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


def safe_load_json(path: Path, default: dict = None) -> dict:
    """Load JSON file with graceful fallback."""
    if default is None:
        default = {}
    try:
        content = path.read_bytes()
        return fast_json_loads(content)
    except (FileNotFoundError, json.JSONDecodeError, IOError, OSError):
        pass  # Expected failures, safe to ignore
    except Exception as e:
        from hooks.hook_utils.logging import log_event
        log_event("safe_load_json", "unexpected_error", {"path": str(path), "error": str(e)})
    return default.copy() if isinstance(default, dict) else default


def safe_save_json(path: Path, data: dict, indent: int = 2) -> bool:
    """Save JSON file with graceful error handling and file locking.

    Note: msgspec doesn't support indent, so we use standard json for pretty-printing.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if indent == 0:
            with open(path, 'wb') as f:
                with file_lock(f):
                    f.write(fast_json_dumps(data))
        else:
            with open(path, 'w') as f:
                with file_lock(f):
                    json.dump(data, f, indent=indent)
        return True
    except (IOError, OSError, TypeError):
        return False


def atomic_write_json(path: Path, data: dict) -> bool:
    """
    Write JSON atomically using temp file + rename.
    More robust than flock alone - survives crashes.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.stem}_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(fast_json_dumps(data))
            os.replace(temp_path, path)
            return True
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise
    except Exception:
        return False


# =============================================================================
# Safe File Operations (from file_ops.py)
# =============================================================================

def safe_stat(path: PathLike) -> os.stat_result | None:
    """Get file stats safely, return None on error."""
    try:
        return os.stat(path)
    except (FileNotFoundError, PermissionError, OSError):
        return None


def safe_mtime(path: PathLike, default: float = 0.0) -> float:
    """Get file modification time safely, return default on error."""
    try:
        return os.path.getmtime(path)
    except (FileNotFoundError, PermissionError, OSError):
        return default


def safe_exists(path: PathLike) -> bool:
    """Check if path exists safely, return False on error."""
    try:
        return os.path.exists(path)
    except (OSError, PermissionError):
        return False


# =============================================================================
# Path Utilities (from paths.py)
# =============================================================================

def normalize_path(path: str) -> str:
    """Normalize path to absolute resolved form."""
    try:
        return str(Path(path).resolve())
    except (OSError, ValueError):
        return path


def expand_path(path: str) -> str:
    """Expand ~, environment variables, and normalize path."""
    expanded = os.path.expandvars(os.path.expanduser(path))
    return os.path.normpath(expanded)
