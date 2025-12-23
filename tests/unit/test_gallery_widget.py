from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from src.core.image_attachment import ImageAttachment
from src.gui.widgets.gallery_widget import GalleryWidget


@pytest.fixture
def mock_main_window():
    window = MagicMock()
    window.worker = MagicMock()
    window.command_requested = MagicMock()
    # Mock signals on worker
    window.worker.attachments_loaded = MagicMock()
    window.worker.attachments_loaded.connect = MagicMock()
    window.worker.command_finished = MagicMock()
    window.worker.command_finished.connect = MagicMock()
    return window


@pytest.fixture
def gallery_widget(mock_main_window, qtbot):
    widget = GalleryWidget(mock_main_window)
    qtbot.addWidget(widget)
    return widget


def test_initialization(gallery_widget, mock_main_window):
    assert gallery_widget.list_widget.count() == 0
    assert not gallery_widget.btn_add.isEnabled()
    mock_main_window.worker.attachments_loaded.connect.assert_called()


def test_set_owner(gallery_widget, mock_main_window):
    # Mock invokeMethod to prevent actual Qt invocation issues or verify it
    # But since it uses QMetaObject.invokeMethod, mocking it is hard without patching QtCore
    # We can check if it enables the button

    with patch("PySide6.QtCore.QMetaObject.invokeMethod") as mock_invoke:
        gallery_widget.set_owner("events", "1")

        assert gallery_widget.owner_type == "events"
        assert gallery_widget.owner_id == "1"
        assert gallery_widget.btn_add.isEnabled()
        mock_invoke.assert_called()


def test_on_attachments_loaded(gallery_widget):
    gallery_widget.set_owner("events", "1")

    att1 = ImageAttachment(
        id="a1",
        owner_type="events",
        owner_id="1",
        image_rel_path="img1.png",
        caption="Caption 1",
    )
    att2 = ImageAttachment(
        id="a2", owner_type="events", owner_id="1", image_rel_path="img2.png"
    )

    # Needs valid path for icon check? The code checks full_path.exists().
    # We should mock Path.exists or get_user_data_path.

    with (
        patch("src.gui.widgets.gallery_widget.get_user_data_path") as mock_path,
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_path.return_value = "/fake/path"

        gallery_widget.on_attachments_loaded("events", "1", [att1, att2])

        assert gallery_widget.list_widget.count() == 2

        items = [
            gallery_widget.list_widget.item(i)
            for i in range(gallery_widget.list_widget.count())
        ]
        item1 = next(i for i in items if i.data(Qt.UserRole) == "a1")
        item2 = next(i for i in items if i.data(Qt.UserRole) == "a2")

        assert item1.text() == "Caption 1"
        assert item2.text() == ""  # No caption


def test_add_clicked(gallery_widget, mock_main_window):
    gallery_widget.set_owner("events", "1")

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileNames",
        return_value=(["/img.png"], "Images"),
    ):
        gallery_widget.btn_add.click()

        mock_main_window.command_requested.emit.assert_called()
        cmd = mock_main_window.command_requested.emit.call_args[0][0]
        assert cmd.__class__.__name__ == "AddImagesCommand"
        assert cmd.source_paths == ["/img.png"]


def test_remove_clicked(gallery_widget, mock_main_window):
    gallery_widget.set_owner("events", "1")
    # Add item manually
    item = MagicMock()
    item.data.return_value = "att1"
    gallery_widget.list_widget.currentItem = MagicMock(return_value=item)

    with patch("PySide6.QtWidgets.QMessageBox.question") as mock_msg:
        # Simulate Yes
        from PySide6.QtWidgets import QMessageBox

        mock_msg.return_value = QMessageBox.Yes

        gallery_widget._on_remove_clicked()

        mock_main_window.command_requested.emit.assert_called()
        cmd = mock_main_window.command_requested.emit.call_args[0][0]
        assert cmd.__class__.__name__ == "RemoveImageCommand"
        assert cmd.attachment_id == "att1"


def test_edit_caption(gallery_widget, mock_main_window):
    gallery_widget.set_owner("events", "1")

    att1 = ImageAttachment(
        id="att1",
        owner_type="events",
        owner_id="1",
        image_rel_path="i.png",
        caption="Old",
    )
    gallery_widget.attachments = [att1]

    item = MagicMock()
    item.data.return_value = "att1"
    gallery_widget.list_widget.currentItem = MagicMock(return_value=item)

    with patch(
        "PySide6.QtWidgets.QInputDialog.getText", return_value=("New Caption", True)
    ):
        gallery_widget._on_edit_caption_clicked()

        mock_main_window.command_requested.emit.assert_called()
        cmd = mock_main_window.command_requested.emit.call_args[0][0]
        assert cmd.__class__.__name__ == "UpdateImageCaptionCommand"
        assert cmd.attachment_id == "att1"
        assert cmd.new_caption == "New Caption"


def test_drop_event(gallery_widget, mock_main_window):
    gallery_widget.set_owner("events", "1")

    event = MagicMock()
    mime = MagicMock()
    url = MagicMock()
    url.isLocalFile.return_value = True
    url.toLocalFile.return_value = "/path/to/image.jpg"
    mime.urls.return_value = [url]
    event.mimeData.return_value = mime

    gallery_widget.dropEvent(event)

    mock_main_window.command_requested.emit.assert_called()
    cmd = mock_main_window.command_requested.emit.call_args[0][0]
    assert cmd.__class__.__name__ == "AddImagesCommand"
    assert "/path/to/image.jpg" in cmd.source_paths
