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
    if getattr(sys, "frozen", False):
        try:
            # Debug logging to identify why paths fail
            # We use a try-block to ensure logging never crashes the app
            log_path = os.path.join(os.path.dirname(sys.executable), "paths_debug.log")

            # Use append mode
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"Request: {relative_path}\n")

                root_path = os.path.dirname(sys.executable)
                f.write(f"  Root: {root_path}\n")

                full_path_root = os.path.join(root_path, relative_path)
                exists_root = os.path.exists(full_path_root)
                f.write(f"  Check Root: {full_path_root} -> {exists_root}\n")

                if exists_root:
                    return full_path_root

                internal_path = os.path.join(root_path, "_internal")
                full_path_internal = os.path.join(internal_path, relative_path)
                exists_internal = os.path.exists(full_path_internal)
                f.write(
                    f"  Check Internal: {full_path_internal} -> {exists_internal}\n"
                )

                if exists_internal:
                    return full_path_internal

                f.write("  FAILED both checks, defaulting to root\n")
                return full_path_root
        except Exception:
            # If logging fails, just fall back to standard behavior (root path)
            pass

        return os.path.join(os.path.dirname(sys.executable), relative_path)
    else:
        # Development mode: resolve relative to this file
        # src/core/paths.py -> src/core -> src -> root
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

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
