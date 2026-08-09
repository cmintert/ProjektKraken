from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


def test_checkbox_style_covers_tree_view():
    """Test that checkbox style includes QTreeView indicators."""
    style = StyleHelper.get_checkbox_style()
    assert "QTreeView::indicator" in style
    assert "QTreeView::indicator:checked" in style


def test_tree_view_style_includes_checkbox_style():
    """Test that tree view style includes checkbox styling."""
    style = StyleHelper.get_tree_view_style()
    assert "QTreeView::indicator" in style
    assert "image: url(" in style  # Check for icon


def test_checked_indicator_uses_primary_background_in_light_modes():
    """The white check icon must contrast with light-theme indicators."""
    theme_manager = ThemeManager()

    for theme_name in ("light_mode", "muted_light_mode"):
        theme_manager.set_theme(theme_name)
        primary = theme_manager.get_theme()["primary"]

        assert f"background-color: {primary}" in StyleHelper.get_checkbox_style()
