"""
File I/O utilities with locking and graceful error handling.
"""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Try to use msgspec for faster JSON
try:
    from config import fast_json_loads, fast_json_dumps, HAS_MSGSPEC
except ImportError:
    import json as _json
    HAS_MSGSPEC = False
    def fast_json_loads(data): return _json.loads(data if isinstance(data, str) else data.decode())
    def fast_json_dumps(obj): return _json.dumps(obj).encode()


@contextmanager
def file_lock(file_handle):
    """
    Context manager for exclusive file locking using fcntl.

    Usage:
        with open(path, 'w') as f:
            with file_lock(f):
                json.dump(data, f)
    """
    try:
        fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        yield file_handle
    finally:
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass


def safe_load_json(path: Path, default: dict = None) -> dict:
    """Load JSON file with graceful fallback.

    Removed redundant path.exists() check - read_bytes() will raise
    FileNotFoundError if file doesn't exist, which is caught below.
    """
    if default is None:
        default = {}
    try:
        content = path.read_bytes()
        if HAS_MSGSPEC:
            return fast_json_loads(content)
        else:
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, IOError, OSError):
        pass
    except Exception:
        # Catch msgspec.DecodeError and other parsing errors
        pass
    return default.copy() if isinstance(default, dict) else default


def safe_save_json(path: Path, data: dict, indent: int = 2) -> bool:
    """Save JSON file with graceful error handling and file locking."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        with open(path, 'a') as f:
            with file_lock(f):
                f.write(json.dumps(entry) + "\n")
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
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2, default=str)
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
