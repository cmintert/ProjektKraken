import pytest

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


def test_load_event(editor):
    ev = Event(id="1", name="Test Event", lore_date=500.0, type="cosmic")
    editor.load_event(ev)

    assert editor.name_edit.text() == "Test Event"
    assert editor.temporal_widget.get_start() == 500.0
    assert editor.isEnabled() is True


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
        ev, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
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
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.update_relation_requested) as blocker:
        editor._on_edit_selected_relation()

    # args: rel_id, target_id, new_type, attributes
    assert blocker.args == ["r1", "new_target", "related_to", {}]


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
