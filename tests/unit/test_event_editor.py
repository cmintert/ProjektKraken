import pytest
from PySide6.QtGui import QTextCursor

from src.core.events import Event
from src.gui.widgets.event_editor import EventEditorWidget


@pytest.fixture
def editor(qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EventEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


def test_editor_init(editor):
    assert editor.name_edit is not None
    assert editor._content_widget.isHidden()  # Hidden until event loaded
    assert not editor._empty_state.isHidden()  # Empty state shown on init


def test_show_world_action_tracks_open_event(editor, qtbot):
    assert not editor.btn_show_world_at_event.isEnabled()
    for event_id in ("first", "second"):
        editor.load_event(Event(id=event_id, name=event_id, lore_date=42.25))
        assert editor.btn_show_world_at_event.isEnabled()
        with qtbot.waitSignal(editor.show_world_at_event_requested) as request:
            editor.btn_show_world_at_event.click()
        assert request.args == [event_id]
    editor.load_event(None)
    assert not editor.btn_show_world_at_event.isEnabled()


def test_show_world_uses_saved_date_and_preserves_event_draft(editor, qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtCore import Qt

    from src.app.coordinators.time_coordinator import TimeCoordinator
    from src.gui.widgets.timeline import TimelineWidget

    event = Event(id="draft", name="Saved", lore_date=-42.25, lore_duration=3.0)
    editor.load_event(event)
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.view.set_playhead_event_snapping(True)
    timeline.set_current_time(100.0)
    window = editor.parent()
    window.event_editor = editor
    window.timeline = timeline
    window.entity_editor = MagicMock()
    window.entity_editor.has_unsaved_changes.return_value = False
    window.entity_editor.current_entity_id = None
    window.data_coordinator = MagicMock()
    window.data_coordinator.cached_events = [event]
    coordinator = TimeCoordinator(window)
    timeline.playhead_time_changed.connect(coordinator.on_playhead_changed)
    map_fanout = MagicMock()
    timeline.playhead_time_changed.connect(map_fanout)
    editor.show_world_at_event_requested.connect(coordinator.show_world_at_event)
    editor.name_edit.setText("Unsaved name")
    date = editor.temporal_widget.date_start.txt_date
    date.setText("unaccepted date")
    date.textEdited.emit(date.text())
    assert editor.temporal_widget.has_pending_draft()
    revision = editor.edit_revision

    qtbot.mouseClick(editor.btn_show_world_at_event, Qt.MouseButton.LeftButton)

    assert timeline.get_playhead_time() == event.lore_date
    assert timeline.get_current_time() == 100.0
    assert editor.current_event_id == event.id
    assert editor.name_edit.text() == "Unsaved name"
    assert date.text() == "unaccepted date"
    assert editor.temporal_widget.has_pending_draft()
    assert editor.edit_revision == revision
    assert editor.has_unsaved_changes()
    assert map_fanout.call_args_list
    assert all(call.args == (event.lore_date,) for call in map_fanout.call_args_list)
    window.data_coordinator.on_graph_playhead_changed.assert_called()
    window.worker.save_current_time.assert_not_called()


def test_load_event(editor):
    ev = Event(id="1", name="Test Event", lore_date=500.0, type="cosmic")
    editor.load_event(ev)

    assert editor.name_edit.text() == "Test Event"
    assert editor.temporal_widget.get_start() == 500.0
    assert editor.isEnabled() is True


def test_save_acknowledgement_does_not_clear_newer_event_draft(editor, qtbot):
    """An older successful save must leave later typing in the live document."""
    ev = Event(id="event-1", name="Event", lore_date=0.0, description="Start")
    editor.load_event(ev)
    inner = editor.desc_edit.editor
    inner.moveCursor(QTextCursor.MoveOperation.End)
    inner.insertPlainText(" one")
    with qtbot.waitSignal(editor.save_requested) as request:
        editor._on_save()
    revision = request.args[0]["__editor_revision"]
    assert editor.has_unsaved_changes()
    inner.insertPlainText(" two")
    newer_revision = editor.edit_revision

    assert newer_revision > revision
    assert not editor.finish_save(revision, True)
    assert editor.has_unsaved_changes()
    assert inner.toPlainText() == "Start one two"

    with qtbot.waitSignal(editor.save_requested) as next_request:
        editor._on_save()
    assert next_request.args[0]["__editor_revision"] == newer_revision
    assert editor.finish_save(newer_revision, True)
    assert not editor.has_unsaved_changes()


def test_failed_event_save_keeps_draft_dirty(editor, qtbot):
    ev = Event(id="event-1", name="Event", lore_date=0.0, description="Start")
    editor.load_event(ev)
    editor.desc_edit.editor.insertPlainText(" more")
    with qtbot.waitSignal(editor.save_requested) as request:
        editor._on_save()
    revision = request.args[0]["__editor_revision"]

    assert not editor.finish_save(revision, False)
    assert editor.has_unsaved_changes()


def test_save_clicked(editor, qtbot):
    ev = Event(id="1", name="Old Name", lore_date=100.0, type="generic")
    editor.load_event(ev)

    # Change Name
    editor.name_edit.setText("New Name")

    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    assert isinstance(saved_data, dict)
    assert saved_data["name"] == "New Name"
    assert saved_data["id"] == "1"


def test_add_relation_flow(editor, qtbot, monkeypatch):
    ev = Event(id="1", name="Source", lore_date=0.0, type="generic")
    editor.load_event(ev)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("target_id", "caused", True, {})

    # Patch the class where it is defined
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.add_relation_requested) as blocker:
        editor.btn_add_rel.click()

    # Signal: source, target, type, attributes, bidirectional
    assert blocker.args == ["1", "target_id", "caused", {}, True]


def test_remove_relation(editor, qtbot, monkeypatch):
    ev = Event(id="1", name="Source", lore_date=0.0)
    editor.load_event(
        ev, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock msgbox
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)

    with qtbot.waitSignal(editor.remove_relation_requested) as blocker:
        editor._on_remove_selected_relation()

    assert blocker.args[0] == "r1"


def test_automatic_mentions_are_read_only(editor):
    ev = Event(id="1", name="Source", lore_date=0.0)
    editor.load_event(
        ev, relations=[{"id": "r1", "target_id": "t1", "rel_type": "mentions"}]
    )
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)
    removed = []
    updated = []
    editor.remove_relation_requested.connect(removed.append)
    editor.update_relation_requested.connect(lambda *args: updated.append(args))

    editor._update_rel_button_states()
    editor._on_remove_relation_item(item)
    editor._on_edit_relation(item)

    assert not editor.btn_remove_rel.isEnabled()
    assert not editor.btn_edit_rel.isEnabled()
    assert removed == []
    assert updated == []


def test_context_menu_actions(editor, qtbot, monkeypatch):
    ev = Event(id="1", name="Source", lore_date=0.0)
    editor.load_event(
        ev,
        relations=[
            {
                "id": "r1",
                "target_id": "t1",
                "target_kind": "entity",
                "rel_type": "caused",
            }
        ],
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("new_target", "related_to", True, {})
    mock_dialog.bi_check = MagicMock()  # For setVisible(False)

    # Patch the class where it is defined
    dialog_kwargs = {}

    def create_dialog(*args, **kwargs):
        dialog_kwargs.update(kwargs)
        return mock_dialog

    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog, "RelationEditDialog", create_dialog
    )

    with qtbot.waitSignal(editor.update_relation_requested) as blocker:
        editor._on_edit_selected_relation()

    # args: rel_id, target_id, new_type, attributes
    assert blocker.args == ["r1", "new_target", "related_to", {}]
    assert dialog_kwargs["target_kind"] == "entity"


def test_wikilink_insertion_has_no_immediate_relation_writer(editor):
    """Wikilinks are reconciled only when the editor is saved."""
    assert not hasattr(editor, "_on_wikilink_added")
    assert not hasattr(editor.desc_edit, "link_added")


def test_sheet_builder_data_loss(editor, qtbot):
    """Test that manipulating the sheet builder updates the attribute editor and
    saves correctly.
    """
    ev = Event(id="1", name="Test", lore_date=0.0, attributes={"Focus": 10})
    editor.load_event(ev)

    # Verify both editors start with the value
    assert editor.attribute_editor.get_attributes()["Focus"] == 10
    assert "Focus" in editor.sheet_builder.get_attributes()
    assert editor.sheet_builder.get_attributes()["Focus"] == 10

    # Modify "Focus" in Sheet Builder
    focus_pair = editor.sheet_builder._pairs["Focus"]
    focus_pair.value_edit.setText("20")

    # Check if Attribute Editor is updated
    assert editor.attribute_editor.get_attributes()["Focus"] == 20

    # Simulate Save
    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    assert saved_data["attributes"]["Focus"] == 20
