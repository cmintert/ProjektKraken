"""Tests for the shared IconPickerDialog.

Validates default icon listing, project icon listing, and import behaviour.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.icon_picker_dialog import (
    IconPickerDialog,
    get_available_default_icons,
    get_project_icons,
)


@pytest.fixture
def qapp():
    """Provides a QApplication instance for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# get_available_default_icons
# ---------------------------------------------------------------------------


class TestGetAvailableDefaultIcons:
    """Tests for the get_available_default_icons helper."""

    def test_returns_list(self):
        """Should return a list (possibly empty if path missing)."""
        result = get_available_default_icons()
        assert isinstance(result, list)

    def test_all_entries_are_svg(self):
        """All returned filenames must end with .svg."""
        for name in get_available_default_icons():
            assert name.endswith(".svg")

    def test_result_is_sorted(self):
        """Returned list must be sorted alphabetically."""
        icons = get_available_default_icons()
        assert icons == sorted(icons)

    @patch(
        "src.gui.dialogs.icon_picker_dialog._get_default_icons_dir",
        return_value="/nonexistent/path",
    )
    def test_missing_directory_returns_empty(self, _mock):
        """Returns empty list when default icons directory does not exist."""
        assert get_available_default_icons() == []


# ---------------------------------------------------------------------------
# get_project_icons
# ---------------------------------------------------------------------------


class TestGetProjectIcons:
    """Tests for get_project_icons."""

    def test_empty_world(self, tmp_path):
        """No icons returned for a world without assets/images."""
        assert get_project_icons(str(tmp_path)) == []

    def test_finds_imported_icons(self, tmp_path):
        """Discovers icon_ prefixed files in assets/images."""
        images_dir = tmp_path / "assets" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "icon_abc123.svg").write_text("<svg/>")
        (images_dir / "icon_def456.png").write_bytes(b"\x89PNG")

        result = get_project_icons(str(tmp_path))
        assert len(result) == 2
        assert "assets/images/icon_abc123.svg" in result
        assert "assets/images/icon_def456.png" in result

    def test_ignores_non_icon_files(self, tmp_path):
        """Files without icon_ prefix are ignored."""
        images_dir = tmp_path / "assets" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "photo_abc.png").write_bytes(b"\x89PNG")
        (images_dir / "icon_ok.svg").write_text("<svg/>")

        result = get_project_icons(str(tmp_path))
        assert len(result) == 1
        assert "icon_ok.svg" in result[0]

    def test_ignores_disallowed_extensions(self, tmp_path):
        """Files with disallowed extensions are ignored."""
        images_dir = tmp_path / "assets" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "icon_bad.exe").write_bytes(b"MZ")

        assert get_project_icons(str(tmp_path)) == []

    def test_result_is_sorted(self, tmp_path):
        """Returned list is sorted alphabetically."""
        images_dir = tmp_path / "assets" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "icon_zzz.svg").write_text("<svg/>")
        (images_dir / "icon_aaa.svg").write_text("<svg/>")

        result = get_project_icons(str(tmp_path))
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# IconPickerDialog construction
# ---------------------------------------------------------------------------


class TestIconPickerDialogCreation:
    """Tests for IconPickerDialog instantiation."""

    def test_creates_without_world_root(self, qapp):
        """Dialog can be created with no world_root."""
        dialog = IconPickerDialog()
        assert dialog.windowTitle() == "Select Icon"
        assert dialog.selected_icon is None

    def test_creates_with_world_root(self, qapp, tmp_path):
        """Dialog can be created with a world_root."""
        dialog = IconPickerDialog(world_root=str(tmp_path))
        assert dialog.selected_icon is None

    def test_selected_icon_set_on_accept(self, qapp):
        """_on_icon_selected stores name and accepts."""
        dialog = IconPickerDialog()
        dialog._on_icon_selected("castle.svg")
        assert dialog.selected_icon == "castle.svg"
