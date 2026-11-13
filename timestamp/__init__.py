"""
Timestamp - Initialization module for AUR installation.

This module defines the base paths for a system installation.
It must be imported before any other timestamp module.
"""

import os
import sys
from pathlib import Path

# Paths for AUR installation
PKG_DIR = Path("/usr/lib/timestamp")

# User configuration directory (XDG compliant)
CONFIG_DIR = Path.home() / ".config" / "timestamp"

# User data directory (XDG compliant)
DATA_DIR = Path.home() / ".local" / "share" / "timestamp"

# User cache directory (XDG compliant)
CACHE_DIR = Path.home() / ".cache" / "timestamp"

# Logs directory
LOGS_DIR = DATA_DIR / "logs"

# Runtime directory
RUNTIME_DIR = DATA_DIR / "runtime"

# Icons directory
ICONS_DIR = Path("/usr/share/icons/hicolor/scalable/apps")


def ensure_directories():
    """Create necessary directories if they don't exist."""
    for directory in [CONFIG_DIR, DATA_DIR, LOGS_DIR, RUNTIME_DIR, CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


# Add package directory to sys.path if needed
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

# Initialize directories
ensure_directories()

# Define variables for other modules
# These variables will be used by backup.config, netshares, etc.
_project_root = CONFIG_DIR
_runtime_root = RUNTIME_DIR

# Export for compatibility
__all__ = [
    'PKG_DIR', 'CONFIG_DIR', 'DATA_DIR', 'CACHE_DIR', 
    'LOGS_DIR', 'RUNTIME_DIR', 'ICONS_DIR',
    '_project_root', '_runtime_root',
    'ensure_directories'
]
