"""Theme and read-only behavior of the wiki reference pane."""

from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_peek_panel import WikiPeekPanel


def test_peek_rethemes_visible_controls_without_losing_content(qtbot):
    panel = WikiPeekPanel()
    qtbot.addWidget(panel)
    panel.resize(500, 400)
    panel.show()
    panel.show_object("entity", "entity-1", "Harbor", "The city description")
    manager = ThemeManager()
    base_theme = manager.get_theme().copy()
    old_themes = manager.themes.copy()
    old_name = manager.current_theme_name
    new_theme = base_theme | {
        "surface": "#162431",
        "text_main": "#E1D9C1",
        "text_dim": "#A1ACB7",
        "border": "#425565",
        "primary": "#7BA9DD",
    }

    try:
        manager.themes["peek_test_theme"] = new_theme
        manager.current_theme_name = "peek_test_theme"
        panel._apply_theme(new_theme)

        assert "#162431" in panel.styleSheet()
        assert "#E1D9C1" in panel.title.styleSheet()
        assert "#A1ACB7" in panel.detail.styleSheet()
        assert "#162431" in panel.description.styleSheet()
        assert "#E1D9C1" in panel.description.styleSheet()
        assert "#162431" in panel.choices.styleSheet()
        assert panel.title.text() == "Harbor"
        assert panel.description.toPlainText() == "The city description"
        viewport = panel.description.viewport()
        background = viewport.grab().toImage().pixelColor(
            viewport.width() - 10, viewport.height() - 10
        )
        assert background.name().lower() == "#162431"
    finally:
        manager.themes = old_themes
        manager.current_theme_name = old_name
