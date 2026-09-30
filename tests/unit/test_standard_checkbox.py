"""Unit tests for StandardCheckbox."""

from PySide6.QtWidgets import QCheckBox

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper

# We expect this import to fail initially or the class to be missing
from src.gui.widgets.standard_buttons import StandardCheckbox


def test_standard_checkbox_init(qtbot):
    """Test that StandardCheckbox initializes with correct defaults."""
    checkbox = StandardCheckbox("Test Checkbox")
    qtbot.addWidget(checkbox)

    assert isinstance(checkbox, QCheckBox)
    assert checkbox.text() == "Test Checkbox"

    # Check that style is applied
    assert checkbox.styleSheet() == StyleHelper.get_checkbox_style()


def test_standard_checkbox_theme_update(qtbot):
    """Test that StandardCheckbox updates style on theme change."""
    tm = ThemeManager()
    checkbox = StandardCheckbox("Theme Test")
    qtbot.addWidget(checkbox)

    initial_style = checkbox.styleSheet()
    assert "color:" in initial_style

    # Apply a temporary test theme
    new_theme = tm.get_theme().copy()
    new_theme["text_main"] = "#FF00FF"  # Distinct color

    previous_theme = tm.current_theme_name
    tm.themes["test_theme_checkbox"] = new_theme
    try:
        tm.current_theme_name = "test_theme_checkbox"
        checkbox._on_theme_changed()

        updated_style = checkbox.styleSheet()
        assert "#FF00FF" in updated_style
        assert updated_style != initial_style
    finally:
        tm.current_theme_name = previous_theme
        del tm.themes["test_theme_checkbox"]


def test_standard_checkbox_no_text(qtbot):
    """Test StandardCheckbox without text."""
    checkbox = StandardCheckbox()
    qtbot.addWidget(checkbox)
    assert checkbox.text() == ""
