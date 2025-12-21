import pytest

from src.core.entities import Entity
from src.gui.widgets.entity_editor import EntityEditorWidget


@pytest.fixture
def editor(qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


def test_editor_init(editor):
    assert editor.name_edit is not None
    assert not editor.isEnabled()  # Disabled until loaded


def test_load_entity(editor):
    ent = Entity(id="1", name="Test Entity", type="Character", description="Desc")
    editor.load_entity(ent)

    assert editor.name_edit.text() == "Test Entity"
    assert editor.type_edit.currentText() == "Character"
    assert editor.desc_edit.toPlainText() == "Desc"
    assert editor.isEnabled() is True


def test_save_clicked(editor, qtbot):
    ent = Entity(id="1", name="Old Name", type="Generic")
    editor.load_entity(ent)

    # Change Name
    editor.name_edit.setText("New Name")

    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    assert isinstance(saved_data, dict)
    assert saved_data["name"] == "New Name"
    assert saved_data["id"] == "1"


def test_add_relation_flow(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(ent)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("target_id", "caused", True)

    # Patch the class where it is defined
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.add_relation_requested) as blocker:
        editor.btn_add_rel.click()

    # Signal: source, target, type, bidirectional
    assert blocker.args == ["1", "target_id", "caused", True]


def test_remove_relation(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(
        ent, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock msgbox
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)

    with qtbot.waitSignal(editor.remove_relation_requested) as blocker:
        editor.btn_remove_rel.click()

    assert blocker.args[0] == "r1"


def test_edit_relation_flow(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(
        ent, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("new_target", "related_to", True)

    # Mock bi_check for setVisible call
    mock_dialog.bi_check = MagicMock()

    # Patch the class
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.update_relation_requested) as blocker:
        editor.btn_edit_rel.click()

    # args: rel_id, target_id, new_type
    assert blocker.args == ["r1", "new_target", "related_to"]
