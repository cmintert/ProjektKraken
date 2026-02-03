from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.core.theme_manager import ThemeManager
from src.gui.widgets.longform.outline import LongformOutlineWidget
from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def theme_manager():
    # Reset singleton if needed or just use current
    tm = ThemeManager()
    return tm


@pytest.fixture
def outline_widget(qtbot):
    widget = LongformOutlineWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def unified_list_widget(qtbot):
    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    return widget


def test_outline_colors_update_on_theme_change(outline_widget, theme_manager):
    # Setup initial items
    sequence = [
        {"table": "events", "id": "1", "name": "Event 1", "meta": {}},
        {"table": "entities", "id": "2", "name": "Entity 1", "meta": {}},
    ]

    # Mock initial theme
    with patch.object(
        ThemeManager,
        "get_theme",
        return_value={"accent_secondary": "#000000", "primary": "#000000"},
    ):
        # Trigger update manually to set initial colors
        outline_widget._update_colors()
        outline_widget.load_sequence(sequence)

        # Check initial colors
        item_event = outline_widget.topLevelItem(0)
        item_entity = outline_widget.topLevelItem(1)

        assert item_event.foreground(0).color().name() == "#000000"
        assert item_entity.foreground(0).color().name() == "#000000"

    # Change theme
    new_theme = {
        "accent_secondary": "#123456",  # Event color
        "primary": "#654321",  # Entity color
    }

    with patch.object(ThemeManager, "get_theme", return_value=new_theme):
        # Emit signal
        theme_manager.theme_changed.emit(new_theme)

        # Check new colors
        assert item_event.foreground(0).color().name() == "#123456"
        assert item_entity.foreground(0).color().name() == "#654321"


def test_unified_list_colors_update_on_theme_change(unified_list_widget, theme_manager):
    # Setup data
    from src.core.entities import Entity
    from src.core.events import Event

    event = Event(id="1", name="Event 1", lore_date=10.0)
    entity = Entity(id="2", name="Entity 1", type="Character")

    # Mock initial theme
    with patch.object(
        ThemeManager,
        "get_theme",
        return_value={"accent_secondary": "#000000", "primary": "#000000"},
    ):
        unified_list_widget.color_event = QColor("#000000")
        unified_list_widget.color_entity = QColor("#000000")
        unified_list_widget.set_data([event], [entity])

        # Check initial colors (filter default is All Items)
        # Note: UnifiedListWidget renders items. We need to find them.
        # It's a DraggableListWidget inside.
        list_w = unified_list_widget.list_widget
        assert list_w.count() >= 2

        # Find items
        item_event = None
        item_entity = None

        for i in range(list_w.count()):
            it = list_w.item(i)
            if it.data(Qt.ItemDataRole.UserRole + 1) == "event":
                item_event = it
            elif it.data(Qt.ItemDataRole.UserRole + 1) == "entity":
                item_entity = it

        assert item_event.foreground().color().name() == "#000000"
        assert item_entity.foreground().color().name() == "#000000"

    # Change theme
    new_theme = {
        "accent_secondary": "#AABBCC",  # Entity color
        "primary": "#DDEEFF",  # Event color
        "text_main": "#FFFFFF",  # Required for checkbox style
        "surface": "#000000",
        "border": "#333333",
        "text_dim": "#888888"
    }

    with patch.object(ThemeManager, "get_theme", return_value=new_theme):
        theme_manager.theme_changed.emit(new_theme)

        # Re-fetch items (list cleared and re-rendered)
        list_w = unified_list_widget.list_widget

        item_event = None
        item_entity = None

        for i in range(list_w.count()):
            it = list_w.item(i)
            if it.data(Qt.ItemDataRole.UserRole + 1) == "event":
                item_event = it
            elif it.data(Qt.ItemDataRole.UserRole + 1) == "entity":
                item_entity = it

        assert item_event.foreground().color().name() == "#aabbcc"
        assert item_entity.foreground().color().name() == "#ddeeff"
