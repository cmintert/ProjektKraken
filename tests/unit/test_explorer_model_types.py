"""Regression tests for Explorer item discriminator integrity."""

import pytest
from PySide6.QtCore import Qt

from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel


def test_explorer_model_renders_discriminated_items(qapp):
    """Valid event and entity variants retain their distinct display paths."""
    event = Event(id="event-1", name="Arrival", lore_date=12.0)
    entity = Entity(id="entity-1", name="Harbor", type="Location")
    model = ExplorerModel()
    model.set_items([("event", event), ("entity", entity)])

    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == (
        "[12.0] Arrival"
    )
    assert model.data(model.index(1, 0), Qt.ItemDataRole.DisplayRole) == (
        "Harbor (Location)"
    )


def test_explorer_model_rejects_mismatched_discriminator(qapp):
    """A mismatched runtime tuple cannot enter the model."""
    model = ExplorerModel()
    entity = Entity(id="entity-1", name="Harbor", type="Location")

    with pytest.raises(TypeError, match="does not match Entity"):
        model.set_items([("event", entity)])  # type: ignore[list-item]
