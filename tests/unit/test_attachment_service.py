from unittest.mock import MagicMock

import pytest

from src.core.image_attachment import ImageAttachment
from src.services.attachment_service import AttachmentService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_store):
    return AttachmentService(mock_repo, mock_store)


def test_add_images(service, mock_repo, mock_store):
    mock_store.import_image.return_value = (
        "rel/path.webp",
        "rel/thumb.webp",
        (100, 100),
    )
    mock_repo.list_by_owner.return_value = []

    source_paths = ["/tmp/img1.png", "/tmp/img2.jpg"]

    created = service.add_images("event", "evt-1", source_paths)

    assert len(created) == 2
    assert mock_store.import_image.call_count == 2
    assert mock_repo.insert.call_count == 2

    assert created[0].owner_id == "evt-1"
    assert created[0].order_index == 0

    assert created[1].order_index == 1


def test_remove_image(service, mock_repo, mock_store):
    att = ImageAttachment(
        id="1", owner_type="event", owner_id="e1", image_rel_path="p", order_index=0
    )
    mock_repo.get.return_value = att
    mock_store.delete_files.return_value = ("trash/p", "trash/t")

    success, info = service.remove_image("1")

    assert success is True
    assert info["img_trash_path"] == "trash/p"
    assert mock_store.delete_files.called
    assert mock_repo.delete.called


def test_restore_image(service, mock_repo, mock_store):
    att = ImageAttachment(
        id="1", owner_type="event", owner_id="e1", image_rel_path="p", order_index=0
    )
    trash_info = {
        "attachment_data": att,
        "img_trash_path": "trash/p",
        "thumb_trash_path": "trash/t",
    }

    service.restore_image(trash_info)

    mock_store.restore_files.assert_called_with("trash/p", "p", "trash/t", None)
    mock_repo.insert.assert_called_with(att)
