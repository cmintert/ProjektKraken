import pytest

from src.core.theme_manager import ThemeManager
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


def test_history_panel_hover_style(history_panel):
    """Test that the hover style is properly set in QSS."""
    theme = ThemeManager().get_theme()
    primary = theme.get("primary", "#4A9EFF")

    qss = history_panel.command_list.styleSheet()
    assert "QListWidget::item:hover" in qss
    if len(primary) == 7 and primary.startswith("#"):
        r = int(primary[1:3], 16)
        g = int(primary[3:5], 16)
        b = int(primary[5:7], 16)
        expected_hover = f"rgba({r}, {g}, {b}, 0.1)"
        assert expected_hover in qss
