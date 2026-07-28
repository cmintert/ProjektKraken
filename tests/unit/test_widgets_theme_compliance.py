from src.core.theme_manager import ThemeManager
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget


def test_compact_date_widget_theme_compliance(qtbot):
    """Test that CompactDateWidget input fields adhere to theme."""
    tm = ThemeManager()
    tm.current_theme_name = "dark_mode"

    widget = CompactDateWidget()
    qtbot.addWidget(widget)

    # Check text date input style
    # Should have input field style + monospace font
    style = widget.txt_date.styleSheet().lower()
    theme = tm.get_theme()
    surface = theme["surface"].lower()
    border = theme["border"].lower()
    text = theme["text_main"].lower()

    assert surface in style
    assert border in style
    assert "consolas" in style

    # The shared date chip owns the surface and border. Its inner controls
    # remain transparent while inheriting the active theme's text color.
    chip_style = widget._date_chip.styleSheet().lower()
    assert surface in chip_style
    assert border in chip_style
    assert "transparent" in widget.spin_year.styleSheet().lower()
    assert text in widget.spin_year.styleSheet().lower()
    assert "transparent" in widget.combo_month.styleSheet().lower()
    assert text in widget.combo_month.styleSheet().lower()

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
        tm.current_theme_name = "test_compliance"
        widget._on_theme_changed(new_theme)

        updated_style = widget.txt_date.styleSheet().lower()
        assert "#abcdef" in updated_style
        assert "#123456" in updated_style

        # The outer chip and its transparent child controls all update.
        assert "#abcdef" in widget._date_chip.styleSheet().lower()
        assert "#000000" in widget.spin_year.styleSheet().lower()

    finally:
        tm.themes = original_themes
        tm.current_theme_name = initial_theme_name


def test_compact_duration_widget_theme_compliance(qtbot):
    """Test that CompactDurationWidget input fields adhere to theme."""
    tm = ThemeManager()
    tm.current_theme_name = "dark_mode"

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
        tm.current_theme_name = "test_compliance_dur"
        widget._on_theme_changed(new_theme)

        # Verify update
        updated_style = widget.spin_years.styleSheet().lower()
        assert "#fedcba" in updated_style

    finally:
        tm.themes = original_themes
        tm.current_theme_name = initial_theme_name
