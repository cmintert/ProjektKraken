"""Tests for database information CLI statistics."""

from unittest.mock import MagicMock

from src.cli.info import gather_stats
from src.core.image_attachment import ImageAttachment
from src.services.db_service import DatabaseService


def test_gather_stats_resolves_attachment_relative_to_world(tmp_path) -> None:
    """Attachment sizes use the canonical relative asset path field."""
    database_path = tmp_path / "World.kraken"
    asset_path = tmp_path / "assets" / "images" / "attachment.webp"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"x" * 1024 * 1024)

    attachment = ImageAttachment(
        id="attachment-id",
        owner_type="entity",
        owner_id="entity-id",
        image_rel_path="assets/images/attachment.webp",
    )
    attachment_repo = MagicMock()
    attachment_repo.list_all.return_value = [attachment]

    db_service = MagicMock(spec=DatabaseService)
    db_service.get_all_entities.return_value = []
    db_service.get_all_events.return_value = []
    db_service.get_connection.return_value = None
    db_service.get_all_maps.return_value = []
    db_service.get_attachment_repo.return_value = attachment_repo
    db_service.get_db_file_path.return_value = str(database_path)
    db_service.get_all_calendar_configs.return_value = []
    db_service.get_all_tags.return_value = []
    db_service.get_timeline_grouping_config.return_value = None

    stats = gather_stats(db_service)

    assert stats["attachments"] == {"count": 1, "total_size_mb": 1.0}
