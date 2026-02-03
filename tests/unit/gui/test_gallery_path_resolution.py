"""
Test for Gallery Widget Path Resolution.

Verifies that the GalleryWidget correctly resolves image paths relative to the
provided project root, rather than falling back to default AppData paths which
causes issues in portable/built versions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.gui.widgets.gallery_widget import GalleryWidget

# Mock get_user_data_path to return a fixed "AppData" location for verification
MOCK_APP_DATA = Path("C:/MockAppData/ProjektKraken")


@pytest.fixture
def mock_paths():
    """Patches get_user_data_path to return a known path."""
    with patch("src.gui.widgets.gallery_widget.get_user_data_path") as mock:
        mock.side_effect = lambda p: str(MOCK_APP_DATA / p)
        yield mock


def test_gallery_path_resolution_logic(qtbot):
    """
    Directly unit test the path resolution method we plan to add.
    """
    main_window = MagicMock()
    widget = GalleryWidget(main_window)

    project_root = Path("C:/Dist/World")

    # Assert set_project_root exists
    assert hasattr(widget, "set_project_root"), "Widget missing set_project_root method"

    widget.set_project_root(project_root)
    assert widget.project_root == project_root

    # Test helper method for resolution (resolve_path)
    rel_path = "assets/test.png"

    # Verify it resolves against project root
    assert hasattr(widget, "_resolve_path"), "Widget missing _resolve_path helper"

    resolved = widget._resolve_path(rel_path)
    assert resolved == project_root / rel_path

    # Verify fallback if project_root is NOT set (legacy behavior)
    widget.set_project_root(None)
    with patch(
        "src.gui.widgets.gallery_widget.get_user_data_path",
        return_value="C:/AppData/Path",
    ):
        resolved_fallback = widget._resolve_path(rel_path)
        # Normalize for windows comparison
        assert Path(resolved_fallback) == Path("C:/AppData/Path")
