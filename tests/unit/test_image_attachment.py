"""
Tests for the ImageAttachment dataclass.
"""

import time

from src.core.image_attachment import ImageAttachment


def test_image_attachment_creation():
    """Test creating an ImageAttachment with required fields."""
    attachment = ImageAttachment(
        id="test-id",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test.jpg",
    )

    assert attachment.id == "test-id"
    assert attachment.owner_type == "event"
    assert attachment.owner_id == "event-123"
    assert attachment.image_rel_path == "assets/images/test.jpg"
    assert attachment.thumb_rel_path is None
    assert attachment.caption is None
    assert attachment.order_index == 0
    assert attachment.resolution is None
    assert attachment.source is None


def test_image_attachment_with_optional_fields():
    """Test creating an ImageAttachment with all optional fields."""
    attachment = ImageAttachment(
        id="test-id",
        owner_type="entity",
        owner_id="entity-456",
        image_rel_path="assets/images/test.jpg",
        thumb_rel_path="assets/thumbnails/test_thumb.jpg",
        caption="Test caption",
        order_index=5,
        resolution=(1920, 1080),
        source="https://example.com/image.jpg",
    )

    assert attachment.thumb_rel_path == "assets/thumbnails/test_thumb.jpg"
    assert attachment.caption == "Test caption"
    assert attachment.order_index == 5
    assert attachment.resolution == (1920, 1080)
    assert attachment.source == "https://example.com/image.jpg"


def test_image_attachment_created_at_default():
    """Test that created_at is automatically set to current time."""
    before = time.time()
    attachment = ImageAttachment(
        id="test-id",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test.jpg",
    )
    after = time.time()

    assert before <= attachment.created_at <= after


def test_is_thumbnail_available_with_thumbnail():
    """Test is_thumbnail_available returns True when thumbnail exists."""
    attachment = ImageAttachment(
        id="test-id",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test.jpg",
        thumb_rel_path="assets/thumbnails/test_thumb.jpg",
    )

    assert attachment.is_thumbnail_available is True


def test_is_thumbnail_available_without_thumbnail():
    """Test is_thumbnail_available returns False when thumbnail is None."""
    attachment = ImageAttachment(
        id="test-id",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test.jpg",
        thumb_rel_path=None,
    )

    assert attachment.is_thumbnail_available is False


def test_is_thumbnail_available_with_empty_string():
    """Test is_thumbnail_available returns False for empty string."""
    attachment = ImageAttachment(
        id="test-id",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test.jpg",
        thumb_rel_path="",
    )

    assert attachment.is_thumbnail_available is False


def test_image_attachment_owner_types():
    """Test creating attachments with different owner types."""
    event_attachment = ImageAttachment(
        id="test-id-1",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test1.jpg",
    )

    entity_attachment = ImageAttachment(
        id="test-id-2",
        owner_type="entity",
        owner_id="entity-456",
        image_rel_path="assets/images/test2.jpg",
    )

    assert event_attachment.owner_type == "event"
    assert entity_attachment.owner_type == "entity"


def test_image_attachment_order_index():
    """Test that order_index can be used for sorting."""
    attachment1 = ImageAttachment(
        id="test-id-1",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test1.jpg",
        order_index=0,
    )

    attachment2 = ImageAttachment(
        id="test-id-2",
        owner_type="event",
        owner_id="event-123",
        image_rel_path="assets/images/test2.jpg",
        order_index=1,
    )

    attachments = sorted([attachment2, attachment1], key=lambda x: x.order_index)
    assert attachments[0].id == "test-id-1"
    assert attachments[1].id == "test-id-2"
