from unittest.mock import patch

import pytest

from src.app.main import MainWindow
from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    from PySide6.QtWidgets import QMessageBox

    with patch("src.app.worker_manager.DatabaseWorker") as MockWorker:
        with (
            patch("src.app.worker_manager.QThread"),
            patch("src.app.main_window.QTimer"),
            patch(
                "src.app.coordinators.editor_coordinator.QMessageBox.warning",
                return_value=QMessageBox.Discard,
            ),
        ):
            # Mock worker and DB
            mock_worker = MockWorker.return_value
            mock_worker.db_service.get_all_events.return_value = []

            window = MainWindow()
            # window.show()  # needed for visibility checks often
            qtbot.addWidget(window)
            yield window


def _connect_creation_flow(window):
    """Connect the deferred signals used by creation in the test window."""
    # The fixture bypasses startup hydration; seed the normal completer snapshot.
    window.event_editor.update_suggestions([])
    window.entity_editor.update_suggestions([])
    window.unified_list.create_entity_requested.connect(
        window.editor_coordinator.create_entity
    )
    window.unified_list.create_event_requested.connect(
        window.editor_coordinator.create_event
    )
    window.data_handler.lore_mutation_ready.connect(
        window.data_coordinator.on_lore_mutation_ready
    )
    window.data_handler.selection_requested.connect(
        window.data_coordinator.on_selection_requested
    )
    window.data_handler.reload_all_data.connect(window.data_coordinator.load_data)
    window.data_handler.suggestion_effects_requested.connect(
        window.data_coordinator.on_suggestion_effects
    )


@pytest.mark.ci_fast
@pytest.mark.parametrize("entity_type", ["Character", "Faction", "Airship"])
def test_real_creation_form_persists_type_and_undo_redo(
    main_window, db_service, monkeypatch, qtbot, entity_type
):
    """The visible creation route persists the authored type in one command."""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QDialogButtonBox

    from src.gui.dialogs.entity_creation_dialog import EntityCreationDialog

    original_exec = EntityCreationDialog.exec

    def fill_dialog(dialog):
        def fill():
            assert dialog.entity_type() == ""
            dialog.name_edit.setText("New lore")
            dialog.type_combo.setEditText(entity_type)
            qtbot.mouseClick(
                dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),
                Qt.MouseButton.LeftButton,
            )

        QTimer.singleShot(0, fill)
        return original_exec(dialog)

    monkeypatch.setattr(EntityCreationDialog, "exec", fill_dialog)
    _connect_creation_flow(main_window)
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    main_window.unified_list.create_entity_requested.emit()
    assert len(commands) == 1
    command = commands[0]
    assert command.select_after_create is True
    assert command.execute(db_service).success
    assert db_service.get_entity(command.entity_id).type == entity_type
    command.undo(db_service)
    assert db_service.get_entity(command.entity_id) is None
    assert command.execute(db_service).success
    assert db_service.get_entity(command.entity_id).type == entity_type


def test_create_cancel_does_nothing(main_window):
    """Test cancelling creation."""
    with patch(
        "src.app.coordinators.editor_coordinator.EntityCreationDialog"
    ) as mock_input:
        mock_input.return_value.exec.return_value = 0

        with patch(
            "src.app.coordinators.editor_coordinator.CreateEntityCommand"
        ) as MockCmd:
            main_window.editor_coordinator.create_entity()
            MockCmd.assert_not_called()
            main_window.worker.run_command.assert_not_called()


def test_explorer_create_opens_new_entity(main_window, db_service):
    """A confirmed Explorer creation becomes the active editable context."""
    _connect_creation_flow(main_window)
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.EntityCreationDialog",
            **{
                "return_value.exec.return_value": 1,
                "return_value.name.return_value": "Tasgillia",
                "return_value.entity_type.return_value": "Character",
            },
        ),
        patch.object(main_window.data_coordinator, "load_entity_details") as load,
    ):
        main_window.unified_list.create_entity_requested.emit()
        assert len(commands) == 1
        result = commands[0].execute(db_service)
        assert result.success
        main_window.data_handler.on_command_finished(result)
        main_window.data_coordinator.on_entity_details_ready(
            db_service.get_entity(commands[0].entity_id), [], []
        )

    entity_id = commands[0].entity_id
    navigation = main_window.navigation_coordinator
    assert navigation.selected_type == "entity"
    assert navigation.selected_id == entity_id
    assert (
        main_window.workspace.active_panel(main_window.workspace.panel_zone("entity"))
        == "entity"
    )
    load.assert_called_once_with(entity_id)
    assert main_window.entity_editor.current_entity_id == entity_id
    current = main_window.unified_list.list_widget.currentIndex()
    source = main_window.unified_list._proxy_model.mapToSource(current)
    assert (
        main_window.unified_list._model.data(source, ExplorerModel.ItemIdRole)
        == entity_id
    )


def test_provisional_create_keeps_origin(main_window, db_service):
    """Provisional creation updates the model without changing editing context."""
    _connect_creation_flow(main_window)
    navigation = main_window.navigation_coordinator
    original_panel = main_window.workspace.active_panel(
        main_window.workspace.panel_zone("entity")
    )
    commands = []
    main_window.command_requested.connect(commands.append)
    with patch.object(main_window.data_coordinator, "load_entity_details") as load:
        navigation._materialize_provisional("entity", "Grey Ford")
        assert len(commands) == 1
        assert commands[0].select_after_create is False
        result = commands[0].execute(db_service)
        assert result.success
        main_window.data_handler.on_command_finished(result)

    assert navigation.selected_id is None
    assert db_service.get_entity(commands[0].entity_id).type == "Concept"
    assert (
        main_window.workspace.active_panel(main_window.workspace.panel_zone("entity"))
        == original_panel
    )
    load.assert_not_called()
    assert any(
        entity.id == commands[0].entity_id
        for entity in main_window.data_coordinator.cached_entities
    )


def _writing_context(window, qtbot, object_id="origin", source_kind="entity"):
    """Prepare a visible unsaved draft and return its observable state reader."""
    from PySide6.QtGui import QTextCursor

    editor = window.entity_editor if source_kind == "entity" else window.event_editor
    if source_kind == "entity":
        editor.load_entity(Entity(id=object_id, name=object_id, type="Character"))
    else:
        editor.load_event(Event(id=object_id, name=object_id, lore_date=1.0))
    navigation = window.navigation_coordinator
    navigation._last_selected_id = object_id
    navigation._last_selected_type = source_kind
    window.workspace.show_panel(source_kind)
    window.show()
    text = editor.desc_edit.editor
    text.setPlainText("Unsaved reference draft\n" * 70)
    cursor = text.textCursor()
    cursor.setPosition(8)
    cursor.setPosition(16, QTextCursor.MoveMode.KeepAnchor)
    text.setTextCursor(cursor)
    text.setFocus()
    qtbot.wait(10)
    text.verticalScrollBar().setValue(20)
    editor.set_dirty(True)

    def state():
        from PySide6.QtWidgets import QApplication

        return (
            navigation.selected_id,
            navigation.selected_type,
            editor.current_entity_id
            if source_kind == "entity"
            else editor.current_event_id,
            text.toPlainText(),
            text.textCursor().anchor(),
            text.textCursor().position(),
            text.verticalScrollBar().value(),
            editor.has_unsaved_changes(),
            QApplication.focusWidget(),
            window.workspace.capture_layout(),
            window.timeline.get_playhead_time(),
        )

    return state


@pytest.mark.ci_fast
@pytest.mark.parametrize("object_type", ["entity", "event"])
@pytest.mark.parametrize("route", ["peek", "feature", "marker"])
@pytest.mark.parametrize("late", [False, True])
@pytest.mark.parametrize("source_kind", ["entity", "event"])
def test_contextual_completion_preserves_live_writing(
    main_window, db_service, qtbot, object_type, route, late, source_kind
):
    """Real mutation delivery retains drafts and never reverses later navigation."""
    from src.commands.composite_command import CompositeCommand
    from src.core.map import Map
    from src.gui.dialogs.map_object_picker_dialog import MapObjectChoice

    _connect_creation_flow(main_window)
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    main_window.command_requested.connect(commands.append)
    main_window.timeline.set_playhead_time(42.75)
    state = _writing_context(main_window, qtbot, source_kind=source_kind)
    widget = main_window.map_widget
    widget.set_maps([Map(id="map-1", name="Map", image_path="")])
    widget.select_map("map-1")
    if route != "peek":
        db_service.insert_map(Map(id="map-1", name="Map", image_path=""))
        main_window.workspace.show_panel("map")
        widget.view.setFocus()
    before = state()
    main_window.editor_coordinator._new_marker_attributes = lambda: {}
    if route == "peek":
        main_window.navigation_coordinator._materialize_provisional(
            object_type, "Grey Ford"
        )
    else:
        choice = MapObjectChoice(
            action="create",
            object_type=object_type,
            name="Grey Ford",
            entity_type="Location",
        )
        with patch.object(widget, "_choose_map_object", return_value=choice):
            if route == "feature":
                widget.create_entity_requested.connect(
                    main_window.editor_coordinator.on_map_create_entity
                )
                widget.create_event_requested.connect(
                    main_window.editor_coordinator.on_map_create_event
                )
                features = []
                widget.feature_created.connect(lambda *args: features.append(args))
                widget.feature_created.connect(main_window.map_handler.on_feature_drawn)
                geometry = [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}]
                feature_type = "region" if object_type == "entity" else "path"
                widget._on_drawing_finished(feature_type, geometry)
                assert len(features) == 1
                assert features[0][-1] == geometry
            else:
                widget.marker_object_creation_requested.connect(
                    main_window.editor_coordinator.on_map_create_marker_object
                )
                widget._on_create_marker_requested(0.3, 0.7)
    assert len(commands) == (2 if route == "feature" else 1)
    command = commands[0]
    create = command.commands[0] if isinstance(command, CompositeCommand) else command
    assert create.select_after_create is False
    restored = type(command).from_dict(command.to_dict())
    child = restored.commands[0] if route == "marker" else restored
    assert child.select_after_create is False
    object_id = create.entity_id if object_type == "entity" else create.event_id
    if route == "feature":
        assert features[0][1] == object_id
    if object_type == "event":
        assert create.event.lore_date == 42.75
    if late:
        editor = (
            main_window.entity_editor
            if source_kind == "entity"
            else main_window.event_editor
        )
        editor.set_dirty(False)
        state = _writing_context(main_window, qtbot, "later-origin", source_kind)
        before = state()
    with (
        patch.object(main_window.data_coordinator, "load_entity_details") as hydrate,
        patch.object(main_window.data_coordinator, "load_event_details") as event_load,
    ):
        for submitted in commands:
            result = submitted.execute(db_service)
            assert result.success, result.message
            main_window.data_handler.on_command_finished(result)
        qtbot.wait(10)
        assert state() == before
        hydrate.assert_not_called()
        event_load.assert_not_called()
    collection = (
        main_window.data_coordinator.cached_entities
        if object_type == "entity"
        else main_window.data_coordinator.cached_events
    )
    assert any(item.id == object_id for item in collection)
    if route in {"marker", "feature"}:
        marker = db_service.get_marker_by_composite("map-1", object_id, object_type)
        assert marker is not None
        if route == "marker":
            assert (marker.x, marker.y) == (0.3, 0.7)
        else:
            assert marker.geometry == geometry
    for submitted in reversed(commands):
        submitted.undo(db_service)
    lookup = db_service.get_entity if object_type == "entity" else db_service.get_event
    assert lookup(object_id) is None
    for submitted in commands:
        assert submitted.execute(db_service).success
    assert lookup(object_id) is not None


def test_explorer_create_opens_new_event(main_window, db_service):
    """Explicit Event creation still selects the object at the viewed date."""
    _connect_creation_flow(main_window)
    main_window.timeline.set_playhead_time(42.75)
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.QInputDialog.getText",
            return_value=("Council", True),
        ),
        patch.object(main_window.data_coordinator, "load_event_details") as load,
    ):
        main_window.unified_list.create_event_requested.emit()
        command = commands[0]
        assert command.select_after_create is True
        main_window.data_handler.on_command_finished(command.execute(db_service))
    assert main_window.navigation_coordinator.selected_id == command.event_id
    assert command.event.lore_date == 42.75
    load.assert_called_once_with(command.event_id)


@pytest.mark.parametrize("object_type", ["entity", "event"])
def test_peek_button_materializes_without_stealing_writing_focus(
    main_window, db_service, qtbot, object_type
):
    """The visible Peek route resolves locally after the author resumes writing."""
    from PySide6.QtCore import Qt

    _connect_creation_flow(main_window)
    state = _writing_context(main_window, qtbot)
    navigation = main_window.navigation_coordinator
    panel = main_window.wiki_peek_panel
    navigation.peek_target("Grey Ford")
    commands = []
    main_window.command_requested.connect(commands.append)
    button = (
        panel.create_entity_button
        if object_type == "entity"
        else panel.create_event_button
    )
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert len(commands) == 1
    main_window.entity_editor.desc_edit.editor.setFocus()
    before = state()
    result = commands[0].execute(db_service)
    assert result.success
    main_window.data_handler.on_command_finished(result)
    qtbot.wait(10)
    assert state() == before
    assert panel.title.text() == "Grey Ford"
    assert panel._item_type == object_type
    assert panel._item_id == result.data["id"]
    assert not panel.create_entity_button.isVisible()
    assert not panel.create_event_button.isVisible()


@pytest.mark.ci_fast
@pytest.mark.parametrize("object_type", ["entity", "event"])
def test_open_missing_link_exposes_creation_in_peek(
    main_window, db_service, qtbot, object_type
):
    """Following an unresolved link exposes both creation choices without navigation."""
    _connect_creation_flow(main_window)
    state = _writing_context(main_window, qtbot)
    navigation = main_window.navigation_coordinator
    main_window.entity_editor.link_clicked.connect(navigation.navigate_writing_link)
    writing = main_window.entity_editor.desc_edit
    writing.set_wiki_text("See [[Grey Ford]] today.")
    cursor = writing.editor.textCursor()
    cursor.setPosition(6)
    writing.editor.setTextCursor(cursor)
    assert writing.action_open_link.isEnabled()
    assert writing.editor.link_target_at_cursor() == "Grey Ford"
    original_text = writing.get_wiki_text()
    writing.action_open_link.trigger()
    panel = main_window.wiki_peek_panel
    assert main_window.workspace.active_panel("right") == "wiki_peek"
    assert panel.create_entity_button.isVisible()
    assert panel.create_event_button.isVisible()
    assert navigation.selected_id == "origin"
    assert writing.get_wiki_text() == original_text
    commands = []
    main_window.command_requested.connect(commands.append)
    button = (
        panel.create_entity_button
        if object_type == "entity"
        else panel.create_event_button
    )
    button.click()
    assert len(commands) == 1
    writing.editor.setFocus()
    before = state()
    main_window.data_handler.on_command_finished(commands[0].execute(db_service))
    qtbot.wait(10)
    assert state() == before
    assert panel._item_type == object_type
    assert panel._item_id
    assert writing.get_wiki_text() == original_text


def test_cancel_and_failure_keep_relation_and_writing_drafts(main_window, qtbot):
    """Cancelling a map picker or failing a create leaves both local drafts intact."""
    from src.commands.base_command import CommandResult
    from src.core.map import Map

    _connect_creation_flow(main_window)
    state = _writing_context(main_window, qtbot)
    authoring = main_window.entity_editor.relation_authoring
    authoring.capture()
    target = authoring.target
    target.setText("Unfinished connection")
    main_window.entity_editor.desc_edit.editor.setFocus()
    before = state()
    widget = main_window.map_widget
    widget.set_maps([Map(id="map-1", name="Map", image_path="")])
    widget.select_map("map-1")
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with patch.object(widget, "_choose_map_object", return_value=None):
        widget._on_create_marker_requested(0.3, 0.7)
        widget._on_drawing_finished("region", [{"x": 0.1, "y": 0.2}])
    main_window.data_handler.on_command_finished(
        CommandResult(
            success=False, command_name="CreateEntityCommand", message="Create failed"
        )
    )
    assert commands == []
    assert state() == before
    assert authoring.capture_open
    assert authoring.target is target
    assert target.text() == "Unfinished connection"
    authoring.cancel()


def test_explorer_create_reveals_entity_hidden_by_search(main_window, db_service):
    """A search from the prior context cannot hide the new selection."""
    _connect_creation_flow(main_window)
    main_window.unified_list.search_bar.setText("unmatched")
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.EntityCreationDialog",
            **{
                "return_value.exec.return_value": 1,
                "return_value.name.return_value": "Tasgillia",
                "return_value.entity_type.return_value": "Character",
            },
        ),
        patch.object(main_window.data_coordinator, "load_entity_details"),
    ):
        main_window.unified_list.create_entity_requested.emit()
        result = commands[0].execute(db_service)
        main_window.data_handler.on_command_finished(result)

    assert main_window.unified_list.search_bar.text() == ""
    assert main_window.unified_list.list_widget.currentIndex().isValid()
    assert main_window.navigation_coordinator.selected_id == commands[0].entity_id


def test_explorer_create_reveals_entity_hidden_by_advanced_filter(
    main_window, db_service
):
    """The selected new entity remains visible despite a previous tag filter."""
    _connect_creation_flow(main_window)
    main_window.unified_list.set_advanced_filter({"include": ["missing"]})
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.EntityCreationDialog",
            **{
                "return_value.exec.return_value": 1,
                "return_value.name.return_value": "Tasgillia",
                "return_value.entity_type.return_value": "Character",
            },
        ),
        patch.object(main_window.data_coordinator, "load_entity_details"),
    ):
        main_window.unified_list.create_entity_requested.emit()
        result = commands[0].execute(db_service)
        main_window.data_handler.on_command_finished(result)

    assert main_window.unified_list.get_advanced_filter_config() == {}
    assert main_window.unified_list.list_widget.currentIndex().isValid()
    assert main_window.navigation_coordinator.selected_id == commands[0].entity_id


def test_select_item_switches_filter_if_needed(main_window):
    """Verify that select_item switches selection if item is hidden."""
    # Use real objects to avoid MagicMock 'name' comparison issues
    test_entity = Entity(id="ent1", name="Entity 1", type="Concept")
    test_event = Event(id="evt1", name="Event 1", lore_date=10.0, type="generic")

    # Pre-populate
    main_window.data_coordinator._cached_entities = [test_entity]
    main_window.data_coordinator._cached_events = [test_event]

    # Set data on unified_list
    main_window.unified_list.set_data(
        main_window.data_coordinator.cached_events,
        main_window.data_coordinator.cached_entities,
    )

    # 1. Set filter to "Entities Only"
    main_window.unified_list.filter_combo.setCurrentText("Entities Only")
    # Verify count - Entities Only shows entities
    model = main_window.unified_list._proxy_model
    assert model.rowCount() == 1

    # 2. Select Event (which is hidden)
    # Patch list_widget.setCurrentIndex to verify it gets called
    with patch.object(
        main_window.unified_list.list_widget, "setCurrentIndex"
    ) as mock_set:
        with patch.object(main_window.unified_list.list_widget, "scrollTo"):
            main_window.unified_list.select_item("event", "evt1")

            # Should have switched filter
            assert main_window.unified_list.filter_combo.currentText() == "All Items"
            assert mock_set.called
