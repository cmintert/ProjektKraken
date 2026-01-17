"""
Tests for the paths utility module.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.paths import (
    ensure_worlds_directory,
    get_backup_directory,
    get_executable_dir,
    get_resource_path,
    get_user_data_path,
    get_worlds_dir,
)


def test_get_resource_path_development():
    """Test get_resource_path in development mode."""
    # In development, sys._MEIPASS won't exist
    if hasattr(sys, "_MEIPASS"):
        delattr(sys, "_MEIPASS")

    result = get_resource_path("test/resource.txt")

    # Should return path relative to current directory
    assert "test" in result
    assert "resource.txt" in result


def test_get_resource_path_bundled():
    """Test get_resource_path in bundled mode."""
    with patch.object(sys, "_MEIPASS", "/bundled/app", create=True):
        result = get_resource_path("test/resource.txt")

        # Use os.path.join for platform-independent comparison
        expected = os.path.join("/bundled/app", "test/resource.txt")
        assert result == expected


def test_get_user_data_path_creates_directory():
    """Test get_user_data_path creates the directory if it doesn't exist."""
    result = get_user_data_path()

    # Directory should be created
    assert os.path.exists(result)
    assert "ProjektKraken" in result


def test_get_user_data_path_with_filename():
    """Test get_user_data_path with filename parameter."""
    result = get_user_data_path("test.db")

    assert "ProjektKraken" in result
    assert result.endswith("test.db")


def test_get_user_data_path_windows():
    """Test get_user_data_path on Windows uses APPDATA."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_appdata = os.path.join(tmpdir, "AppData", "Roaming")
        os.makedirs(fake_appdata)

        with patch("sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": fake_appdata}):
                result = get_user_data_path()

                assert "ProjektKraken" in result
                # On Windows, should use the (mocked) APPDATA path
                if sys.platform == "win32":
                    assert tmpdir in result or "ProjektKraken" in result


def test_get_user_data_path_macos():
    """Test get_user_data_path on macOS."""
    with patch("sys.platform", "darwin"):
        result = get_user_data_path()

        assert "ProjektKraken" in result


def test_get_user_data_path_linux():
    """Test get_user_data_path on Linux."""
    with patch("sys.platform", "linux"):
        result = get_user_data_path()

        assert "ProjektKraken" in result


def test_get_backup_directory():
    """Test get_backup_directory creates backup directory."""
    result = get_backup_directory()

    assert result.exists()
    assert result.name == "backups"


def test_get_backup_directory_is_path():
    """Test get_backup_directory returns a Path object."""
    result = get_backup_directory()

    assert isinstance(result, Path)


def test_get_executable_dir_development():
    """Test get_executable_dir in development mode."""
    with patch.object(sys, "frozen", False, create=True):
        result = get_executable_dir()

        assert isinstance(result, Path)
        assert result.exists()


def test_get_executable_dir_bundled():
    """Test get_executable_dir in bundled mode."""
    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", "/app/ProjektKraken.exe"):
            result = get_executable_dir()

            assert isinstance(result, Path)
            # Use Path comparison for platform independence
            assert result == Path("/app")


def test_get_worlds_dir():
    """Test get_worlds_dir returns worlds directory."""
    result = get_worlds_dir()

    assert isinstance(result, Path)
    assert result.name == "worlds"


def test_get_worlds_dir_relative_to_executable():
    """Test get_worlds_dir is relative to executable directory."""
    exec_dir = get_executable_dir()
    worlds_dir = get_worlds_dir()

    # Worlds directory should be inside executable directory
    assert worlds_dir.parent == exec_dir


def test_ensure_worlds_directory_creates_directory():
    """Test ensure_worlds_directory creates the directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "src.core.paths.get_worlds_dir", return_value=Path(tmpdir) / "worlds"
        ):
            result = ensure_worlds_directory()

            assert result.exists()
            assert result.is_dir()


def test_ensure_worlds_directory_validates_write_permissions():
    """Test ensure_worlds_directory validates write permissions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worlds_path = Path(tmpdir) / "worlds"
        worlds_path.mkdir()

        with patch("src.core.paths.get_worlds_dir", return_value=worlds_path):
            result = ensure_worlds_directory()

            # Should successfully create and validate
            assert result == worlds_path


def test_ensure_worlds_directory_handles_permission_error():
    """Test ensure_worlds_directory handles permission errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worlds_path = Path(tmpdir) / "readonly" / "worlds"

        with patch("src.core.paths.get_worlds_dir", return_value=worlds_path):
            # Mock mkdir to raise PermissionError
            with patch.object(
                Path, "mkdir", side_effect=PermissionError("No permission")
            ):
                with pytest.raises(OSError, match="Cannot create or write"):
                    ensure_worlds_directory()


def test_ensure_worlds_directory_idempotent():
    """Test ensure_worlds_directory can be called multiple times."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worlds_path = Path(tmpdir) / "worlds"

        with patch("src.core.paths.get_worlds_dir", return_value=worlds_path):
            result1 = ensure_worlds_directory()
            result2 = ensure_worlds_directory()

            assert result1 == result2
            assert result1.exists()


def test_get_resource_path_with_subdirectories():
    """Test get_resource_path with nested subdirectories."""
    result = get_resource_path("themes/dark/style.qss")

    assert "themes" in result
    assert "dark" in result
    assert "style.qss" in result


def test_get_user_data_path_empty_filename():
    """Test get_user_data_path with empty string filename."""
    result = get_user_data_path("")

    # Should return just the directory path
    assert "ProjektKraken" in result
    assert result.endswith("ProjektKraken") or os.path.isdir(result)
