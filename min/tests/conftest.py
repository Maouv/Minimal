"""
Pytest configuration for min/tests.
Adds min/backend to sys.path so flat imports work.
"""

import sys
from pathlib import Path

# Get the backend directory path
BACKEND_DIR = Path(__file__).parent.parent / "backend"

# Add to sys.path if not already there
backend_str = str(BACKEND_DIR.resolve())
if backend_str not in sys.path:
    sys.path.insert(0, backend_str)
