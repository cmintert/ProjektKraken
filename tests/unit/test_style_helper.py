"""
Unit tests for StyleHelper.

Tests that StyleHelper methods return theme-aware QSS strings and that
styles change when ThemeManager switches themes.
"""

import pytest

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


@pytest.fixture
def theme_manager():
    """
    Provides a ThemeManager instance for testing.

    Returns the singleton instance (which is initialized from themes.json).
    """
    return ThemeManager()


def test_empty_state_style_contains_theme_values(theme_manager):
    """Test that empty state style includes theme text_dim color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_empty_state_style()

    assert theme["text_dim"] in style
    assert "font-size" in style
    assert "color:" in style


def test_preview_label_style_contains_theme_values(theme_manager):
    """Test that preview label style includes theme text_dim color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_preview_label_style()

    assert theme["text_dim"] in style
    assert "italic" in style
    assert "color:" in style


def test_error_label_style_contains_theme_values(theme_manager):
    """Test that error label style includes theme error color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_error_label_style()

    assert theme["error"] in style
    assert "bold" in style
    assert "color:" in style


def test_section_header_style():
    """Test that section header style is consistent."""
    style = StyleHelper.get_section_header_style()
    assert "bold" in style


def test_frame_style_contains_theme_values(theme_manager):
    """Test that frame style includes theme border color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_frame_style()

    assert theme["border"] in style
    assert "QFrame" in style
    assert "border:" in style


def test_lore_frame_style_contains_theme_values(theme_manager):
    """Test that lore frame style includes theme colors."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_lore_frame_style()

    assert theme["surface"] in style
    assert theme["border"] in style
    assert theme["accent_secondary"] in style
    assert "QFrame#LoreFrame" in style


def test_map_viewport_style_contains_theme_values(theme_manager):
    """Test that map viewport style includes theme primary color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_map_viewport_style()

    assert theme["primary"] in style
    assert "QFrame#MapViewport" in style


def test_primary_button_style_contains_theme_values(theme_manager):
    """Test that primary button style includes theme primary color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_primary_button_style()

    assert theme["primary"] in style
    assert "QPushButton" in style
    assert "background-color:" in style


def test_destructive_button_style_contains_theme_values(theme_manager):
    """Test that destructive button style includes theme error color."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_destructive_button_style()

    assert theme["error"] in style
    assert "QPushButton" in style
    assert "background-color:" in style


def test_dialog_button_style_selected(theme_manager):
    """Test dialog button style for selected state."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_dialog_button_style(selected=True)

    assert theme["primary"] in style
    assert "day_btn_selected" in style


def test_dialog_button_style_unselected(theme_manager):
    """Test dialog button style for unselected state."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_dialog_button_style(selected=False)

    assert theme["border"] in style
    assert theme["text_main"] in style
    assert "day_btn" in style


def test_dialog_base_style_contains_theme_values(theme_manager):
    """Test that dialog base style includes theme colors."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_dialog_base_style()

    assert theme["app_bg"] in style
    assert theme["text_main"] in style
    assert "QDialog" in style


def test_scrollbar_style_contains_theme_values(theme_manager):
    """Test that scrollbar style includes theme scrollbar colors."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_scrollbar_style()

    assert theme["scrollbar_bg"] in style
    assert theme["scrollbar_handle"] in style
    assert "QScrollBar" in style


def test_wiki_link_style_valid(theme_manager):
    """Test wiki link style for valid links."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_wiki_link_style(broken=False)

    assert theme["accent_secondary"] in style
    assert "underline" in style


def test_wiki_link_style_broken(theme_manager):
    """Test wiki link style for broken links."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_wiki_link_style(broken=True)

    assert theme["error"] in style
    assert "underline" in style


def test_timeline_header_style_contains_theme_values(theme_manager):
    """Test that timeline header style includes theme colors."""
    theme = theme_manager.get_theme()
    style = StyleHelper.get_timeline_header_style()

    assert theme["surface"] in style
    assert theme["border"] in style
    assert "background-color:" in style


def test_style_changes_with_theme_switch(theme_manager):
    """Test that StyleHelper outputs change when theme switches."""
    # Get style with current theme
    original_theme_name = theme_manager.current_theme_name
    original_style = StyleHelper.get_empty_state_style()
    original_theme = theme_manager.get_theme()

    # Switch to a different theme
    available_themes = theme_manager.get_available_themes()
    if len(available_themes) < 2:
        pytest.skip("Need at least 2 themes for this test")

    # Find a different theme
    new_theme_name = None
    for theme_name in available_themes:
        if theme_name != original_theme_name:
            new_theme_name = theme_name
            break

    if not new_theme_name:
        pytest.skip("Could not find alternate theme")

    # Switch theme
    theme_manager.set_theme(new_theme_name)
    new_style = StyleHelper.get_empty_state_style()
    new_theme = theme_manager.get_theme()

    # Verify styles are different if theme colors differ
    if original_theme["text_dim"] != new_theme["text_dim"]:
        assert original_style != new_style
        assert new_theme["text_dim"] in new_style

    # Restore original theme
    theme_manager.set_theme(original_theme_name)


def test_apply_standard_list_spacing():
    """Test that apply_standard_list_spacing sets correct values."""
    from PySide6.QtWidgets import QVBoxLayout

    layout = QVBoxLayout()
    StyleHelper.apply_standard_list_spacing(layout)

    assert layout.spacing() == 8
    margins = layout.contentsMargins()
    assert margins.left() == 16
    assert margins.top() == 16
    assert margins.right() == 16
    assert margins.bottom() == 16


def test_apply_compact_spacing():
    """Test that apply_compact_spacing sets correct values."""
    from PySide6.QtWidgets import QVBoxLayout

    layout = QVBoxLayout()
    StyleHelper.apply_compact_spacing(layout)

    assert layout.spacing() == 4
    margins = layout.contentsMargins()
    assert margins.left() == 8
    assert margins.top() == 8
    assert margins.right() == 8
    assert margins.bottom() == 8


def test_apply_form_spacing():
    """Test that apply_form_spacing sets correct values."""
    from PySide6.QtWidgets import QVBoxLayout

    layout = QVBoxLayout()
    StyleHelper.apply_form_spacing(layout)

    assert layout.spacing() == 8
    margins = layout.contentsMargins()
    assert margins.left() == 12
    assert margins.top() == 12
    assert margins.right() == 12
    assert margins.bottom() == 12


def test_apply_no_margins():
    """Test that apply_no_margins removes all margins."""
    from PySide6.QtWidgets import QVBoxLayout

    layout = QVBoxLayout()
    layout.setContentsMargins(16, 16, 16, 16)  # Set some margins first
    StyleHelper.apply_no_margins(layout)

    margins = layout.contentsMargins()
    assert margins.left() == 0
    assert margins.top() == 0
    assert margins.right() == 0
    assert margins.bottom() == 0


@pytest.mark.parametrize(
    "method_name",
    [
        "get_empty_state_style",
        "get_preview_label_style",
        "get_error_label_style",
        "get_frame_style",
        "get_lore_frame_style",
        "get_map_viewport_style",
        "get_primary_button_style",
        "get_destructive_button_style",
        "get_dialog_base_style",
        "get_scrollbar_style",
        "get_timeline_header_style",
    ],
)
def test_style_methods_return_non_empty_strings(method_name):
    """Test that all style methods return non-empty strings."""
    method = getattr(StyleHelper, method_name)
    style = method()
    assert isinstance(style, str)
    assert len(style) > 0


def test_ui_constants_exist():
    """Test that ui_constants module provides expected constants."""
    from src.app.ui_constants import Margins, Spacing

    # Test Spacing constants
    assert Spacing.COMPACT == 4
    assert Spacing.STANDARD == 8
    assert Spacing.WIDE == 12
    assert Spacing.SECTION == 16
    assert Spacing.LARGE_SECTION == 24
    assert Spacing.EXTRA_LARGE == 32

    # Test Margins constants
    assert Margins.NONE == 0
    assert Margins.COMPACT == 8
    assert Margins.STANDARD == 16
    assert Margins.WIDE == 24
    assert Margins.EXTRA_WIDE == 32


def test_empty_state_widget_initialization(qapp):
    """Test that EmptyStateWidget initializes correctly."""
    from src.gui.widgets.empty_state_widget import EmptyStateWidget

    widget = EmptyStateWidget("Test Message")
    assert widget.text() == "Test Message"
    assert not widget.isVisible()  # Should be hidden by default


def test_empty_state_widget_set_message(qapp):
    """Test that EmptyStateWidget can update its message."""
    from src.gui.widgets.empty_state_widget import EmptyStateWidget

    widget = EmptyStateWidget("Initial")
    widget.set_message("Updated")
    assert widget.text() == "Updated"
