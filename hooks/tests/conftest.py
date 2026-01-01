"""
Pytest configuration for hooks tests.

Adds the hooks directory to sys.path so tests can import hook modules.
"""
import sys
from pathlib import Path

# Add hooks directory to path for imports
hooks_dir = Path(__file__).parent.parent
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))
