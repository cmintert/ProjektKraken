import json
import os

import pytest
from fastapi.testclient import TestClient

from src.services.db_service import DatabaseService
from src.services.longform_builder import insert_or_update_longform_meta
from src.webserver.config import ServerConfig
from src.webserver.server import create_app


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_longform_web.db")


@pytest.fixture
def db_service(test_db_path):
    service = DatabaseService(test_db_path)
    service.connect()

    # Let's switch to using objects to be safe and ensure tags are processed.
    from src.core.events import Event

    e1 = Event(
        id="e1",
        name="Event A",
        description="Content A",
        lore_date=100.0,
        attributes={"_tags": ["A"]},
    )
    e2 = Event(
        id="e2",
        name="Event B",
        description="Content B",
        lore_date=200.0,
        attributes={"_tags": ["B"]},
    )

    service.insert_event(e1)
    service.insert_event(e2)

    # Manually populate tags table and event_tags table
    import time

    now = time.time()

    # Insert tags
    service._connection.execute(
        "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)", ("tag_A", "A", now)
    )
    service._connection.execute(
        "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)", ("tag_B", "B", now)
    )

    # Insert event_tags
    service._connection.execute(
        "INSERT INTO event_tags (event_id, tag_id, created_at) VALUES (?, ?, ?)",
        ("e1", "tag_A", now),
    )
    service._connection.execute(
        "INSERT INTO event_tags (event_id, tag_id, created_at) VALUES (?, ?, ?)",
        ("e2", "tag_B", now),
    )
    service._connection.commit()

    # Add to longform
    insert_or_update_longform_meta(service._connection, "events", "e1", position=100.0)
    insert_or_update_longform_meta(service._connection, "events", "e2", position=200.0)

    yield service
    service.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def client(test_db_path, db_service):  # dependent on db_service to ensure data is there
    config = ServerConfig(db_path=test_db_path)
    app = create_app(config)
    return TestClient(app)


def test_get_longform_no_filter(client):
    response = client.get("/api/longform")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sections"]) == 2
    ids = {item["id"] for item in data["sections"]}
    assert "e1" in ids
    assert "e2" in ids


def test_get_longform_filter_tag_A(client):
    filter_config = {"include": ["A"]}  # Changed to dict, will be dumped by params
    # Must explicitly allow passing this config if the server expects it
    # server expects ?filter=...
    response = client.get(
        "/api/longform", params={"filter_json": json.dumps(filter_config)}
    )
    assert response.status_code == 200
    data = response.json()
    # Should contain only Event A
    assert len(data["sections"]) == 1
    assert "Event A" in data["sections"][0]["html"]


def test_get_longform_filter_tag_B(client):
    filter_config = {"include": ["B"], "include_mode": "any"}
    response = client.get(
        "/api/longform", params={"filter_json": json.dumps(filter_config)}
    )
    assert response.status_code == 200
    data = response.json()
    # Should contain only Event B
    assert len(data["sections"]) == 1
    assert "Event B" in data["sections"][0]["html"]


def test_get_longform_invalid_filter_json(client):
    response = client.get("/api/longform", params={"filter_json": "{invalid"})
    assert response.status_code == 200
    # Current logic: catches JSONDecodeError, logs warning, allows_ids remains None
    # -> returns all.
    data = response.json()
    assert len(data["sections"]) == 2
