"""
File I/O utilities with locking and graceful error handling.
"""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from hooks.config import fast_json_loads, fast_json_dumps


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
        pass
    except Exception:
        pass
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


def safe_append_jsonl(path: Path, entry: dict) -> bool:
    """Append entry to JSONL file with graceful error handling and file locking."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'ab') as f:
            with file_lock(f):
                f.write(fast_json_dumps(entry) + b"\n")
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
