import sqlite3

import pytest

from src.core.image_attachment import ImageAttachment
from src.services.repositories.attachment_repository import AttachmentRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS image_attachments (
    id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    image_rel_path TEXT NOT NULL,
    thumb_rel_path TEXT,
    caption TEXT,
    order_index INTEGER NOT NULL,
    created_at REAL DEFAULT (unixepoch()),
    resolution TEXT,
    source TEXT
);
"""


@pytest.fixture
def db_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_connection):
    return AttachmentRepository(db_connection)


def test_insert_and_get(repo):
    att = ImageAttachment(
        id="test-1",
        owner_type="event",
        owner_id="evt-1",
        image_rel_path="assets/img.webp",
        thumb_rel_path="assets/thumb.webp",
        caption="Test Image",
        order_index=0,
        resolution=(800, 600),
        source="/tmp/source.png",
    )
    repo.insert(att)

    fetched = repo.get("test-1")
    assert fetched is not None
    assert fetched.id == "test-1"
    assert fetched.caption == "Test Image"
    assert fetched.resolution == (800, 600)


def test_list_by_owner(repo):
    repo.insert(
        ImageAttachment(
            id="1",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p1",
            order_index=0,
        )
    )
    repo.insert(
        ImageAttachment(
            id="2",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p2",
            order_index=1,
        )
    )
    repo.insert(
        ImageAttachment(
            id="3",
            owner_type="entity",
            owner_id="ent-1",
            image_rel_path="p3",
            order_index=0,
        )
    )

    events = repo.list_by_owner("event", "evt-1")
    assert len(events) == 2
    assert events[0].id == "1"
    assert events[1].id == "2"

    entities = repo.list_by_owner("entity", "ent-1")
    assert len(entities) == 1


def test_delete(repo):
    repo.insert(
        ImageAttachment(
            id="1",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p1",
            order_index=0,
        )
    )
    repo.delete("1")
    assert repo.get("1") is None


def test_update_caption(repo):
    repo.insert(
        ImageAttachment(
            id="1",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p1",
            order_index=0,
            caption="Old",
        )
    )
    repo.update_caption("1", "New")
    fetched = repo.get("1")
    assert fetched.caption == "New"


def test_update_order(repo):
    repo.insert(
        ImageAttachment(
            id="1",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p1",
            order_index=0,
        )
    )
    repo.insert(
        ImageAttachment(
            id="2",
            owner_type="event",
            owner_id="evt-1",
            image_rel_path="p2",
            order_index=1,
        )
    )

    repo.update_order("event", "evt-1", ["2", "1"])

    sorted_atts = repo.list_by_owner("event", "evt-1")
    assert sorted_atts[0].id == "2"
    assert sorted_atts[0].order_index == 0
    assert sorted_atts[1].id == "1"
    assert sorted_atts[1].order_index == 1
