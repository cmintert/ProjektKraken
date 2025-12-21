"""
Path Utility Module.
Handles resource path resolution for both development and bundled environments.
Also manages user data directories for persistent storage.
"""

import os
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    Resolves the absolute path to a resource file.
    Works for both development (venv) and PyInstaller bundled application.

    Args:
        relative_path: The relative path to the resource from project root.

    Returns:
        str: The absolute path to the resource.
    """
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def get_user_data_path(filename: str = "") -> str:
    """
    Returns the absolute path to a file in the user's application data directory.
    Creates the directory if it doesn't exist.

    Args:
        filename: Optional filename to append to the directory path.

    Returns:
        str: Absolute path to the user data directory or file.
    """
    app_name = "ProjektKraken"

    if sys.platform == "win32":
        base_dir = Path(
            os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        )
    elif sys.platform == "darwin":
        base_dir = Path(os.path.expanduser("~/Library/Application Support"))
    else:
        base_dir = Path(os.path.expanduser("~/.local/share"))

    data_dir = base_dir / app_name
    data_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        return str(data_dir / filename)
    return str(data_dir)
