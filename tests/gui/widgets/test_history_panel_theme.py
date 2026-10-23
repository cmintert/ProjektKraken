import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.history_panel import HistoryPanelWidget


@pytest.fixture
def history_panel(qtbot):
    # Ensure we start with a known theme
    ThemeManager().set_theme("dark_mode")
    widget = HistoryPanelWidget()
    qtbot.addWidget(widget)
    return widget


def test_history_panel_theme_refresh(history_panel, qtbot):
    """Test that history panel items update their colors when the theme changes."""
    # Add a command snapshot to history (dicts, not command objects)
    snapshot = {"description": "Mock command", "timestamp": None}
    history_panel.update_history([snapshot], [])

    assert history_panel.command_list.count() == 1

    # Get initial theme text color
    initial_theme = ThemeManager().get_theme()
    initial_color = initial_theme.get("text_main").lower()

    # Verify initial item color
    item = history_panel.command_list.item(0)
    assert item.foreground().color().name().lower() == initial_color

    # Change theme using ThemeManager.set_theme
    ThemeManager().set_theme("light_mode")

    # Verify item color updated (fetch new item since old one was deleted on refresh)
    new_theme = ThemeManager().get_theme()
    new_color = new_theme.get("text_main").lower()

    new_item = history_panel.command_list.item(0)
    assert new_item is not None
    assert new_item.foreground().color().name().lower() == new_color
    assert new_color != initial_color


def test_history_surfaces_follow_every_theme(history_panel, qapp):
    """Rendered workspace and row backgrounds follow live palette changes."""
    manager = ThemeManager()
    history_panel.resize(700, 320)
    history_panel.show()
    history_panel.update_history(
        [{"description": f"Command {i}"} for i in range(40)],
        [{"description": "Undone command"}],
    )
    for name in manager.themes:
        manager.set_theme(name)
        qapp.processEvents()
        theme = manager.get_theme()
        image = history_panel.grab().toImage()
        assert image.pixelColor(0, 0) == QColor(theme["app_bg"])
        viewport = history_panel.command_list.viewport()
        row = history_panel.command_list.visualItemRect(
            history_panel.command_list.item(0)
        )
        assert viewport.grab().toImage().pixelColor(
            QPoint(viewport.width() - 20, row.center().y())
        ) == QColor(theme["surface"])
        assert history_panel.command_list.item(0).foreground().color() == QColor(
            theme["supporting_text"]
        )
        assert history_panel.undo_btn.styleSheet() == (
            StyleHelper.get_secondary_button_style()
        )
        assert history_panel.redo_btn.styleSheet() == (
            StyleHelper.get_secondary_button_style()
        )


def test_theme_switch_preserves_history_position(history_panel, qapp):
    """Recoloring preserves history scroll, focus and detached snapshots."""
    undo = [{"description": f"Command {i}"} for i in range(80)]
    redo = [{"description": "Undone command"}]
    history_panel.resize(350, 300)
    history_panel.show()
    history_panel.update_history(undo, redo)
    history_panel.command_list.setCurrentRow(30)
    history_panel.command_list.setFocus()
    qapp.processEvents()
    scrollbar = history_panel.command_list.verticalScrollBar()
    position = scrollbar.value()
    assert position > 0
    focused = qapp.focusWidget()

    ThemeManager().set_theme("light_mode")
    qapp.processEvents()

    assert scrollbar.value() == position
    assert history_panel.command_list.currentRow() == 30
    assert qapp.focusWidget() is focused
    assert history_panel._undo_stack == undo
    assert history_panel._redo_stack == redo
