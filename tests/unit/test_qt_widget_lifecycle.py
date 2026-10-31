"""Registered Qt roots survive callbacks and support explicit deletion."""

import gc
import weakref

import pytest
import shiboken6
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.ci_fast


def test_registered_window_survives_collection_during_queued_measurement(
    qapp, qtbot, monkeypatch
):
    import src.gui.widgets.wrapping_buttons as wrapping
    from src.gui.widgets.timeline import TimelineWidget

    measured = []
    original = wrapping._geometry

    def geometry(button, size=None):
        gc.collect()
        assert shiboken6.isValid(button)
        measured.append(True)
        return original(button, size)

    def register_window():
        window = TimelineWidget()
        qtbot.addWidget(window)
        window.action_toolbar._schedule_refresh()
        return weakref.ref(window)

    reference = register_window()
    monkeypatch.setattr(wrapping, "_geometry", geometry)
    qapp.processEvents()
    assert measured
    assert reference() is not None
    assert shiboken6.isValid(reference())


@pytest.mark.parametrize("method", ["addWidget", "add_widget"])
def test_registered_widget_can_be_explicitly_deleted(qtbot, method):
    window = QWidget()
    getattr(qtbot, method)(window)
    shiboken6.delete(window)
    assert not shiboken6.isValid(window)
    # Keep the invalid wrapper alive until after pytest-qt's teardown begins.
    qtbot._explicitly_deleted_window = window
