from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

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

    # Change theme - include all required keys
    new_theme = {
        "accent_secondary": "#123456",  # Event color
        "primary": "#654321",  # Entity color
        "destructive": "#FF0000",  # Required for DestructiveButton
        "app_bg": "#000000",  # Required for GraphicsScene
        "text_main": "#FFFFFF",
        "surface": "#000000",
        "border": "#333333",
        "text_dim": "#888888"
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

    # The UnifiedListWidget now uses a model that manages colors internally
    # We'll verify the model colors update on theme change
    model = unified_list_widget._model
    
    # Mock initial theme with all required keys
    initial_theme = {
        "accent_secondary": "#000000",
        "primary": "#000000",
        "text_main": "#FFFFFF",  # Required for checkbox style
        "surface": "#000000",
        "border": "#333333",
        "text_dim": "#888888",
        "app_bg": "#000000",  # Required for timeline scene
        "destructive": "#FF0000",  # Required for DestructiveButton
    }
    
    with patch.object(ThemeManager, "get_theme", return_value=initial_theme):
        # Trigger theme change to set initial colors
        theme_manager.theme_changed.emit(initial_theme)
        unified_list_widget.set_data([event], [entity])

        # Check initial colors via model
        proxy = unified_list_widget._proxy_model
        assert proxy.rowCount() >= 2

        # Find event and entity indices
        event_idx = None
        entity_idx = None
        for i in range(proxy.rowCount()):
            idx = proxy.index(i, 0)
            source_idx = proxy.mapToSource(idx)
            item_type = model.data(source_idx, model.ItemTypeRole)
            if item_type == "event":
                event_idx = idx
            elif item_type == "entity":
                entity_idx = idx

        # Check colors through model
        event_color = proxy.data(event_idx, Qt.ItemDataRole.ForegroundRole).color()
        entity_color = proxy.data(entity_idx, Qt.ItemDataRole.ForegroundRole).color()
        assert event_color.name() == "#000000"
        assert entity_color.name() == "#000000"

    # Change theme
    new_theme = {
        "accent_secondary": "#aabbcc",  # Event color
        "primary": "#ddeeff",  # Entity color
        "text_main": "#FFFFFF",  # Required for checkbox style
        "surface": "#000000",
        "border": "#333333",
        "text_dim": "#888888",
        "app_bg": "#000000",  # Required for timeline scene
        "destructive": "#FF0000",  # Required for DestructiveButton
    }

    with patch.object(ThemeManager, "get_theme", return_value=new_theme):
        theme_manager.theme_changed.emit(new_theme)

        # Re-check colors - model should have updated
        proxy = unified_list_widget._proxy_model

        # Find items again
        event_idx = None
        entity_idx = None
        for i in range(proxy.rowCount()):
            idx = proxy.index(i, 0)
            source_idx = proxy.mapToSource(idx)
            item_type = model.data(source_idx, model.ItemTypeRole)
            if item_type == "event":
                event_idx = idx
            elif item_type == "entity":
                entity_idx = idx

        # Check updated colors
        event_color = proxy.data(event_idx, Qt.ItemDataRole.ForegroundRole).color()
        entity_color = proxy.data(entity_idx, Qt.ItemDataRole.ForegroundRole).color()
        assert event_color.name() == "#aabbcc"
        assert entity_color.name() == "#ddeeff"
