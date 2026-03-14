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
