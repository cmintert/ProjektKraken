from unittest.mock import patch

import pytest

from src.app.main_window import MainWindow
from src.core.entities import Entity
from src.core.events import Event

# Common patches needed for headless MainWindow testing
MAIN_WINDOW_PATCHES = [
    patch("src.app.worker_manager.DatabaseWorker"),
    patch("src.app.worker_manager.QThread"),
    patch("src.app.main_window.QTimer"),
    patch("src.app.ui_manager.UIManager.create_timeline_menu"),
    patch("src.app.ui_manager.UIManager.create_settings_menu"),
    patch("src.app.ui_manager.UIManager.create_file_menu"),
    patch("src.app.ui_manager.UIManager.create_view_menu"),
    patch("src.app.ui_manager.UIManager.create_layouts_menu"),
]


def test_longform_selection_reflects_in_unified_list(qtbot):
    """Verify longform outline selection syncs to unified list."""
    for p in MAIN_WINDOW_PATCHES:
        p.start()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        # Manually connect signals normally handled by ConnectionManager
        window.longform_editor.item_selected.connect(
            window.navigation_coordinator.on_item_selected
        )

        # Populate Unified List
        event = Event(id="evt1", name="Test Event", lore_date=10.0)
        entity = Entity(id="ent1", name="Test Entity", type="Character")
        window.unified_list.set_data([event], [entity])

        model = window.unified_list._proxy_model
        assert model.rowCount() == 2

        # Populate Longform Editor
        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Chapter 1",
                "meta": {},
                "heading_level": 1,
            },
            {
                "table": "entities",
                "id": "ent1",
                "name": "Character Intro",
                "meta": {},
                "heading_level": 1,
            },
        ]
        window.longform_editor.load_sequence(sequence)

        # Select item in Longform Outline
        outline = window.longform_editor.outline
        item = outline.topLevelItem(0)
        outline.setCurrentItem(item)

        # NavigationCoordinator.on_item_selected is timer-based.
        # Trigger the pending selection directly since QTimer is mocked.
        window.navigation_coordinator._perform_delayed_selection()

        # Verify Unified List reflects the selection
        selection_model = window.unified_list.list_widget.selectionModel()
        selected_indexes = selection_model.selectedIndexes()
        assert len(selected_indexes) == 1

        selected_idx = selected_indexes[0]
        source_idx = model.mapToSource(selected_idx)
        source_model = model.sourceModel()
        item_id = source_model.data(source_idx, source_model.ItemIdRole)
        item_type = source_model.data(source_idx, source_model.ItemTypeRole)

        assert item_id == "evt1"
        assert item_type == "event"
    finally:
        for p in MAIN_WINDOW_PATCHES:
            p.stop()
