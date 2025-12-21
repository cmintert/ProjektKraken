from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from src.commands.base_command import CommandResult
from src.gui.widgets.gallery_widget import GalleryWidget


# Mock Worker to signal
class MockWorker(QObject):
    attachments_loaded = Signal(str, str, list)
    command_finished = Signal(object)

    def __init__(self):
        super().__init__()


# Mock MainWindow
class MockMainWindow(QWidget):
    command_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.worker = MockWorker()


@pytest.fixture
def gallery_widget(qtbot):
    mw = MockMainWindow()
    widget = GalleryWidget(mw)
    qtbot.addWidget(widget)
    widget.set_owner("event", "e1")

    # We need to mock the worker's invokeMethod or verify that set_owner calls invokeMethod
    # or just verify connections.
    # Actually set_owner uses QMetaObject.invokeMethod(worker, "load_attachments"...)
    # This is hard to mock directly without patching QMetaObject or using a real worker object's slot logic.
    # But here we want to test on_command_finished.

    return widget, mw


def test_refresh_on_finish(gallery_widget, qtbot):
    widget, mw = gallery_widget

    # Mock set_owner to track calls
    widget.set_owner = MagicMock(wraps=widget.set_owner)

    # 1. Relevant Command (AddImages)
    res = CommandResult(True, "Added", command_name="AddImagesCommand")
    res.data = {"owner_type": "event", "owner_id": "e1"}

    mw.worker.command_finished.emit(res)

    # Needs process events?
    # Direct signal collection
    widget.set_owner.assert_called_with("event", "e1")
    widget.set_owner.reset_mock()

    # 2. Irrelevant Owner
    res = CommandResult(True, "Added", command_name="AddImagesCommand")
    res.data = {"owner_type": "event", "owner_id": "e2"}  # Different ID

    mw.worker.command_finished.emit(res)
    widget.set_owner.assert_not_called()

    # 3. Relevant Attachment (Remove)
    # Give widget an attachment "a1"
    from src.core.image_attachment import ImageAttachment

    att = ImageAttachment(
        id="a1",
        owner_type="event",
        owner_id="e1",
        image_rel_path="assets/a1.png",
        order_index=0,
        source="test",
    )
    widget.attachments = [att]

    res = CommandResult(True, "Removed", command_name="RemoveImageCommand")
    # Missing data first
    # mw.worker.command_finished.emit(res)
    # widget.set_owner.assert_not_called()

    # With data
    res.data = {"attachment_id": "a1"}
    mw.worker.command_finished.emit(res)
    widget.set_owner.assert_called_with("event", "e1")
