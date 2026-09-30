from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit


def test_on_theme_changed_forces_rerender(qtbot):
    """Test that changing the theme forces a re-render of the HTML content with new colors."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Setup ThemeManager
    tm = ThemeManager()

    # Store original themes to restore later (good practice)
    original_themes = tm.themes.copy()
    original_current = tm.current_theme_name
    base_theme = tm.get_theme().copy()

    try:
        # Inject test themes
        tm.themes = {
            "test_theme_a": base_theme | {
                "text_main": "#AAAAAA",
                "accent_secondary": "#BBBBBB",
                "font_size_body": "10pt",
                "font_size_h1": "18pt",
                "font_size_h2": "16pt",
                "font_size_h3": "14pt",
                "scrollbar_bg": "#000000",
                "scrollbar_handle": "#111111",
                "primary": "#222222",
                "surface": "#333333",
                "border": "#444444",
                "destructive": "#ff4444",  # Required key
                "app_bg": "#111111",  # Required for GraphicsScene
                "text_dim": "#888888",
            },
            "test_theme_b": base_theme | {
                "text_main": "#CCCCCC",
                "accent_secondary": "#DDDDDD",
                "font_size_body": "10pt",
                "font_size_h1": "18pt",
                "font_size_h2": "16pt",
                "font_size_h3": "14pt",
                "scrollbar_bg": "#000000",
                "scrollbar_handle": "#111111",
                "primary": "#222222",
                "surface": "#333333",
                "border": "#444444",
                "destructive": "#ff4444",  # Required key
                "app_bg": "#111111",  # Required for GraphicsScene
                "text_dim": "#888888",
            },
        }

        # Start with test_theme_a
        tm.current_theme_name = "test_theme_a"
        widget.editor._on_theme_changed(tm.get_theme())

        # Set text
        widget.set_wiki_text("Test Content")

        # Check HTML has test_theme_a color
        html_a = widget.toHtml().lower()
        assert "#aaaaaa" in html_a
        assert "#cccccc" not in html_a

        # Switch the widget's rendered theme without restyling every live Qt widget.
        tm.current_theme_name = "test_theme_b"
        widget.editor._on_theme_changed(tm.get_theme())

        # Check HTML has test_theme_b color
        html_b = widget.toHtml().lower()
        assert "#cccccc" in html_b
        assert "#aaaaaa" not in html_b

    finally:
        # Restore original themes
        tm.themes = original_themes
        tm.current_theme_name = original_current
