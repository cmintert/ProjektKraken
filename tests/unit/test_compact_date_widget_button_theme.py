from src.core.theme_manager import ThemeManager
from src.gui.widgets.compact_date_widget import CompactDateWidget


def test_calendar_button_styling_applied(qtbot):
    """Test that the calendar button has the icon button style applied."""
    tm = ThemeManager()
    tm.set_theme("dark_mode")

    widget = CompactDateWidget()
    qtbot.addWidget(widget)

    # Check if styleSheet contains expected button styling components
    stylesheet = widget.btn_calendar.styleSheet().lower()
    theme = tm.get_theme()

    surface = theme["surface"].lower()
    border = theme["border"].lower()

    assert "qpushbutton" in stylesheet
    assert surface in stylesheet
    assert border in stylesheet


def test_calendar_button_styling_updates_on_theme_change(qtbot):
    """Test that the button styling re-applies on theme change."""
    tm = ThemeManager()

    # Store original themes to restore
    original_themes = tm.themes.copy()
    original_current = tm.current_theme_name
    base_theme = tm.get_theme().copy()

    try:
        # Inject a test theme
        test_theme = base_theme | {
            "surface": "#112233",
            "border": "#445566",
            "text_main": "#778899",
            "accent_secondary": "#aabbcc",
            "app_bg": "#000000",
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
        tm.themes["test_theme_styling"] = test_theme

        widget = CompactDateWidget()
        qtbot.addWidget(widget)

        # Switch theme properly
        tm.set_theme("test_theme_styling")

        # Verify stylesheet updated with new colors
        updated_style = widget.btn_calendar.styleSheet().lower()

        assert "#112233" in updated_style
        assert "#445566" in updated_style

    finally:
        # Restore
        tm.themes = original_themes
        tm.set_theme(original_current)
