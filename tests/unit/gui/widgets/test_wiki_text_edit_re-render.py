from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from tests.unit.test_visual_presentation import layout_formats


def test_on_theme_changed_refreshes_transient_colors(qtbot):
    """Theme refresh changes layout presentation without rewriting authored HTML."""
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
            "test_theme_a": base_theme
            | {
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
            "test_theme_b": base_theme
            | {
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

        html_a = widget.toHtml()
        undo_steps = widget.editor.document().availableUndoSteps()
        colors_a = {
            f.format.foreground().color().name() for f in layout_formats(widget.editor)
        }
        assert "#aaaaaa" in colors_a
        assert "#cccccc" not in colors_a

        # Switch the widget's rendered theme without restyling every live Qt widget.
        tm.current_theme_name = "test_theme_b"
        widget.editor._on_theme_changed(tm.get_theme())

        colors_b = {
            f.format.foreground().color().name() for f in layout_formats(widget.editor)
        }
        assert "#cccccc" in colors_b
        assert "#aaaaaa" not in colors_b
        assert widget.toHtml() == html_a
        assert widget.editor.document().availableUndoSteps() == undo_steps

    finally:
        # Restore original themes
        tm.themes = original_themes
        tm.current_theme_name = original_current
