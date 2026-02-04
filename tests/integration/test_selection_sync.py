from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from src.app.main_window import MainWindow
from src.core.entities import Entity
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    # Mocking dependencies to avoid full app startup
    with (
        patch("src.app.main_window.ConnectionManager"),
        patch("src.app.main_window.FastInjectManager"),
        patch("src.app.main_window.UIManager"),
        patch("src.app.main_window.TimeCoordinator"),
        patch("src.app.main_window.BackupCoordinator"),
        patch("src.app.main_window.FastInjectCoordinator"),
        patch("src.app.main_window.get_worlds_dir", return_value="."),
    ):

        window = MainWindow()
        qtbot.addWidget(window)

        # Manually verify or setup coordinators if mocked too hard
        # We need NavigationCoordinator to be real or at least functional
        # MainWindow initializes NavigationCoordinator in __init__

        return window


def test_longform_selection_reflects_in_unified_list(qtbot):
    # 1. Setup minimal MainWindow parts needed
    # We need NavigationCoordinator, UnifiedList, LongformEditor
    # The MainWindow __init__ creates them.

    # But we mocked UIManager which holds references to docks/widgets?
    # No, MainWindow creates widgets first, THEN UIManager setups docks.
    # So window.unified_list and window.longform_editor exist.

    # We need to manually connect signals because ConnectionManager is mocked
    window = MainWindow()
    qtbot.addWidget(window)

    # Manually connect signals normally handled by ConnectionManager
    window.longform_editor.item_selected.connect(
        window.navigation_coordinator.on_item_selected
    )

    # We verified ConnectionManager DOES this, so this manual step replicates reality
    # for the isolated test environment.

    # 2. Populate Unified List
    event = Event(id="evt1", name="Test Event", lore_date=10.0)
    entity = Entity(id="ent1", name="Test Entity", type="Character")

    window.unified_list.set_data([event], [entity])

    # Verify items are in list
    model = window.unified_list._proxy_model
    assert model.rowCount() == 2

    # 3. Populate Longform Editor
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

    # 4. Select item in Longform Outline
    # We need to find the item in outline
    outline = window.longform_editor.outline
    item = outline.topLevelItem(0)  # Should be evt1

    # Trigger selection
    outline.setCurrentItem(item)

    # 5. Check if Unified List selection updated
    # This might be async or immediate. Signals are synchronous by default in single thread.

    selection_model = window.unified_list.list_widget.selectionModel()
    selected_indexes = selection_model.selectedIndexes()
    assert len(selected_indexes) == 1

    # Get item data through model
    selected_idx = selected_indexes[0]
    source_idx = model.mapToSource(selected_idx)
    source_model = model.sourceModel()
    item_id = source_model.data(source_idx, source_model.ItemIdRole)
    item_type = source_model.data(source_idx, source_model.ItemTypeRole)
    
    assert item_id == "evt1"
    assert item_type == "event"
