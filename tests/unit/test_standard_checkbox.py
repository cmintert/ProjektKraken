"""Unit tests for StandardCheckbox."""

import pytest
from PySide6.QtWidgets import QCheckBox

# We expect this import to fail initially or the class to be missing
from src.gui.widgets.standard_buttons import StandardCheckbox
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper

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
    
    # Store original theme to restore later if needed (ThemeManager is singleton though)
    # For this test, we rely on the fact that we can just set a new theme
    
    # We need to register this theme to set it by name, 
    # or if ThemeManager allows setting dict directly (it usually requires a name)
    
    tm.themes["test_theme_checkbox"] = new_theme
    tm.set_theme("test_theme_checkbox")
    
    # Check if style updated
    updated_style = checkbox.styleSheet()
    assert "#FF00FF" in updated_style
    assert updated_style != initial_style
    
    # Restore default (optional but good practice)
    tm.set_theme("dark_mode")

def test_standard_checkbox_no_text(qtbot):
    """Test StandardCheckbox without text."""
    checkbox = StandardCheckbox()
    qtbot.addWidget(checkbox)
    assert checkbox.text() == ""
