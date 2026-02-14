from PySide6.QtCore import Qt

from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel


def test_explorer_model_checkbox_persistence():
    model = ExplorerModel()
    event1 = Event(id="e1", name="Event 1", lore_date=100)
    entity1 = Entity(id="ent1", name="Entity 1", type="Character")

    model.set_items([("event", event1), ("entity", entity1)])

    index_e1 = model.index(0, 0)
    index_ent1 = model.index(1, 0)

    # Pre-condition: initially unchecked
    assert (
        model.data(index_e1, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
    )
    assert (
        model.data(index_ent1, Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Unchecked
    )

    # Check item 1
    model.setData(index_e1, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert model.data(index_e1, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    assert (
        model.data(index_ent1, Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Unchecked
    )

    # Check item 2
    model.setData(index_ent1, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert (
        model.data(index_ent1, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    )

    # Uncheck item 1
    model.setData(index_e1, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
    assert (
        model.data(index_e1, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
    )
    assert (
        model.data(index_ent1, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    )

    # Verify get_checked_items
    checked = model.get_checked_items()
    assert len(checked) == 1
    assert checked[0] == ("entity", "ent1")


def test_explorer_model_persistence_across_reset():
    model = ExplorerModel()
    event1 = Event(id="e1", name="Event 1", lore_date=100)
    model.set_items([("event", event1)])

    index = model.index(0, 0)
    model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)

    # Reset model with same ID
    model.set_items([("event", event1)])
    index = model.index(0, 0)
    assert model.data(index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
