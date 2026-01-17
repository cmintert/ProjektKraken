"""
Path Utility Module.
Handles resource path resolution for both development and bundled environments.
Also manages user data directories for persistent storage.

In portable-only mode (0.6.0+), worlds are stored next to the executable in a
worlds/ directory rather than in the system's AppData folder.
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

    Note: For Microsoft Store Python installations, APPDATA is virtualized.
    We detect and resolve the actual path to handle this correctly.

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

    # Check for Microsoft Store Python sandbox on Windows
    real_data_dir = (
        _resolve_ms_store_path(data_dir) if sys.platform == "win32" else data_dir
    )

    if filename:
        return str(real_data_dir / filename)
    return str(real_data_dir)


def _resolve_ms_store_path(virtualized_path: Path) -> Path:
    """
    Resolves virtualized AppData path to actual filesystem path.

    Microsoft Store Python redirects APPDATA writes to a sandboxed
    LocalCache folder. This function detects and returns the real path.

    Args:
        virtualized_path: The virtualized path Python sees.

    Returns:
        Path: The actual filesystem path (either sandboxed or original).
    """
    # Create a temporary marker file to find the real location
    marker_name = ".path_marker_temp"
    marker = virtualized_path / marker_name

    try:
        marker.touch()

        # Check if we're running in MS Store Python sandbox
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        packages_dir = local_appdata / "Packages"

        if packages_dir.exists():
            for pkg in packages_dir.iterdir():
                if "PythonSoftwareFoundation" in pkg.name:
                    # Check for the marker in the sandbox location
                    sandbox_path = (
                        pkg / "LocalCache" / "Roaming" / virtualized_path.name
                    )
                    sandbox_marker = sandbox_path / marker_name
                    if sandbox_marker.exists():
                        # Clean up marker and return the real path
                        marker.unlink(missing_ok=True)
                        return sandbox_path

        # No sandbox detected, use original path
        marker.unlink(missing_ok=True)
        return virtualized_path

    except (OSError, PermissionError):
        # If we can't create marker, just return the original path
        return virtualized_path


def get_default_layout_path() -> str:
    """
    Returns the absolute path to the default layout file.
    Default layout is stored in src/assets/default_layout.json.
    """
    return get_resource_path(os.path.join("src", "assets", "default_layout.json"))


def get_backup_directory() -> Path:
    """
    Returns the backup directory, creating it if necessary.

    Returns:
        Path: Path to the backups directory in user data folder.
    """
    backup_dir = Path(get_user_data_path()) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_executable_dir() -> Path:
    """
    Returns the directory containing the executable or main script.

    For development: Returns the project root directory.
    For PyInstaller: Returns the directory containing the .exe.

    Returns:
        Path: Directory containing the executable.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running in development - return project root
        # Assumes this file is at src/core/paths.py
        return Path(__file__).parent.parent.parent


def get_worlds_dir() -> Path:
    """
    Returns the worlds directory for portable-only mode.

    The worlds directory is created next to the executable and contains
    all world subdirectories. Each world is a self-contained folder with
    its own database, manifest, and assets.

    Returns:
        Path: Path to the worlds/ directory.
    """
    executable_dir = get_executable_dir()
    worlds_dir = executable_dir / "worlds"
    return worlds_dir


def ensure_worlds_directory() -> Path:
    """
    Ensures the worlds directory exists and is writable.

    Creates the worlds/ directory next to the executable if it doesn't exist.
    Validates write permissions.

    Returns:
        Path: Path to the worlds/ directory.

    Raises:
        OSError: If the directory cannot be created or is not writable.
    """
    worlds_dir = get_worlds_dir()

    try:
        worlds_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions with a temporary marker file
        test_file = worlds_dir / ".write_test"
        test_file.touch()
        test_file.unlink()

        return worlds_dir

    except (OSError, PermissionError) as e:
        raise OSError(
            f"Cannot create or write to worlds directory at {worlds_dir}. "
            f"Please ensure the application has write permissions. Error: {e}"
        )
