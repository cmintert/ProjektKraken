from src.core.theme_manager import ThemeManager
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget


def test_compact_date_widget_theme_compliance(qtbot):
    """Test that CompactDateWidget input fields adhere to theme."""
    tm = ThemeManager()
    tm.set_theme("dark_mode")

    widget = CompactDateWidget()
    qtbot.addWidget(widget)

    # Check text date input style
    # Should have input field style + monospace font
    style = widget.txt_date.styleSheet().lower()
    theme = tm.get_theme()
    surface = theme["surface"].lower()
    border = theme["border"].lower()

    assert surface in style
    assert border in style
    assert "consolas" in style

    # Check other inputs
    assert surface in widget.spin_year.styleSheet().lower()
    assert surface in widget.combo_month.styleSheet().lower()

    # Change theme and verify update
    new_theme = {
        "surface": "#abcdef",
        "border": "#123456",
        "text_main": "#000000",
        "accent_secondary": "#555555",
        "app_bg": "#111111",
        "primary": "#ff9900",
        "error": "#ff0000",
        "destructive": "#ff4444",  # Required key
        "text_dim": "#999999",
        "scrollbar_bg": "#222222",
        "scrollbar_handle": "#333333",
        "font_size_h1": "14pt",
        "font_size_h2": "12pt",
        "font_size_h3": "11pt",
        "font_size_body": "10pt",
    }
    # Mock theme change
    original_themes = tm.themes.copy()
    initial_theme_name = tm.current_theme_name

    try:
        tm.themes["test_compliance"] = new_theme
        tm.set_theme("test_compliance")

        updated_style = widget.txt_date.styleSheet().lower()
        assert "#abcdef" in updated_style
        assert "#123456" in updated_style

        # Check other inputs updated too
        assert "#abcdef" in widget.spin_year.styleSheet().lower()

    finally:
        tm.themes = original_themes
        tm.set_theme(initial_theme_name)


def test_compact_duration_widget_theme_compliance(qtbot):
    """Test that CompactDurationWidget input fields adhere to theme."""
    tm = ThemeManager()
    tm.set_theme("dark_mode")

    widget = CompactDurationWidget()
    qtbot.addWidget(widget)

    theme = tm.get_theme()
    surface = theme["surface"].lower()

    # Check spinboxes
    assert surface in widget.spin_years.styleSheet().lower()
    assert surface in widget.spin_months.styleSheet().lower()

    # Change theme
    new_theme = {
        "surface": "#fedcba",
        "border": "#654321",
        "text_main": "#111111",
        "text_dim": "#222222",
        "app_bg": "#333333",
        "accent_secondary": "#444444",
        "primary": "#ff9900",
        "error": "#ff0000",
        "destructive": "#ff4444",  # Required key
        "scrollbar_bg": "#222222",
        "scrollbar_handle": "#333333",
        "font_size_h1": "14pt",
        "font_size_h2": "12pt",
        "font_size_h3": "11pt",
        "font_size_body": "10pt",
    }

    original_themes = tm.themes.copy()
    initial_theme_name = tm.current_theme_name

    try:
        tm.themes["test_compliance_dur"] = new_theme
        tm.set_theme("test_compliance_dur")

        # Verify update
        updated_style = widget.spin_years.styleSheet().lower()
        assert "#fedcba" in updated_style

    finally:
        tm.themes = original_themes
        tm.set_theme(initial_theme_name)
