"""Security regression tests for embedded longform publishing."""

import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.longform_builder import insert_or_update_longform_meta
from src.webserver.config import ServerConfig
from src.webserver.server import _AccessCodeRateLimiter, create_app


@pytest.fixture
def published_db_path(tmp_path) -> str:
    """Create a file-backed world with one published and one unindexed event."""
    path = str(tmp_path / "published.kraken")
    service = DatabaseService(path)
    service.connect()
    service.insert_event(
        Event(
            id="published",
            name="Published",
            description="Visible content",
            lore_date=1.0,
            attributes={"marker": "published"},
        )
    )
    service.insert_event(
        Event(
            id="unindexed",
            name="Unindexed",
            description="Must not be indexed by HTTP",
            lore_date=2.0,
            attributes={"marker": "unchanged"},
        )
    )
    assert service._connection is not None
    insert_or_update_longform_meta(
        service._connection,
        "events",
        "published",
        position=100.0,
    )
    service.close()
    return path


def test_server_config_defaults_to_localhost() -> None:
    config = ServerConfig()

    assert config.host == "127.0.0.1"
    assert config.lan_access is False
    assert config.access_code is None


@pytest.mark.parametrize("code", [None, "1234567", "123456789", "abcdefgh"])
def test_lan_config_requires_eight_digit_code(code: str | None) -> None:
    with pytest.raises(ValueError, match="eight-digit"):
        ServerConfig(lan_access=True, access_code=code)


def test_local_mode_does_not_require_authentication(published_db_path: str) -> None:
    client = TestClient(create_app(ServerConfig(db_path=published_db_path)))

    response = client.get("/api/longform")

    assert response.status_code == 200
    assert [section["id"] for section in response.json()["sections"]] == [
        "published"
    ]


@pytest.mark.parametrize(
    "path",
    ["/api/theme", "/api/tags", "/api/toc", "/api/longform"],
)
def test_lan_mode_protects_every_api_endpoint(
    published_db_path: str, path: str
) -> None:
    config = ServerConfig(
        host="0.0.0.0",
        db_path=published_db_path,
        lan_access=True,
        access_code="01234567",
    )
    client = TestClient(create_app(config))

    missing = client.get(path)
    wrong = client.get(path, headers={"Authorization": "Bearer 76543210"})
    valid = client.get(path, headers={"Authorization": "Bearer 01234567"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200


def test_lan_viewer_shell_and_health_remain_public(published_db_path: str) -> None:
    config = ServerConfig(
        host="0.0.0.0",
        db_path=published_db_path,
        lan_access=True,
        access_code="01234567",
    )
    client = TestClient(create_app(config))

    viewer = client.get("/longform")
    assert viewer.status_code == 200
    assert "LAN access required" in viewer.text
    assert "window.__LAN_ACCESS__ = true" in viewer.text
    assert "01234567" not in viewer.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/health").status_code == 200


def test_failed_access_codes_are_rate_limited(published_db_path: str) -> None:
    config = ServerConfig(
        host="0.0.0.0",
        db_path=published_db_path,
        lan_access=True,
        access_code="01234567",
    )
    client = TestClient(create_app(config))

    for _ in range(4):
        response = client.get(
            "/api/theme", headers={"Authorization": "Bearer 99999999"}
        )
        assert response.status_code == 401

    successful = client.get(
        "/api/theme", headers={"Authorization": "Bearer 01234567"}
    )
    limited = client.get(
        "/api/theme", headers={"Authorization": "Bearer 99999999"}
    )

    assert successful.status_code == 200
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


def test_rate_limiter_has_a_global_failure_bound() -> None:
    limiter = _AccessCodeRateLimiter()

    for index in range(29):
        assert limiter.record_failure(f"client-{index}") is None

    assert limiter.record_failure("client-29") is not None


def test_http_get_does_not_index_missing_items(published_db_path: str) -> None:
    before = _event_attributes(published_db_path, "unindexed")
    client = TestClient(create_app(ServerConfig(db_path=published_db_path)))

    response = client.get("/api/longform")

    assert response.status_code == 200
    assert _event_attributes(published_db_path, "unindexed") == before
    assert "_longform" not in before


def test_read_only_database_skips_initialization_and_rejects_writes(
    published_db_path: str,
) -> None:
    service = DatabaseService(published_db_path, read_only=True)
    with (
        patch.object(service, "_init_schema") as init_schema,
        patch.object(service, "_run_migrations") as run_migrations,
    ):
        service.connect()

    init_schema.assert_not_called()
    run_migrations.assert_not_called()
    assert service._connection is not None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        service._connection.execute(
            "UPDATE events SET name = ? WHERE id = ?", ("Changed", "published")
        )
    service.close()


@pytest.mark.parametrize("doc_id", ["bad/id", "a" * 65, "white space"])
def test_invalid_doc_id_returns_422(
    published_db_path: str, doc_id: str
) -> None:
    client = TestClient(create_app(ServerConfig(db_path=published_db_path)))

    response = client.get("/api/longform", params={"doc_id": doc_id})

    assert response.status_code == 422


def test_maximum_length_doc_id_is_accepted(published_db_path: str) -> None:
    client = TestClient(create_app(ServerConfig(db_path=published_db_path)))

    response = client.get("/api/longform", params={"doc_id": "a" * 64})

    assert response.status_code == 200


def _event_attributes(db_path: str, event_id: str) -> dict:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT attributes FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        return json.loads(row[0])
    finally:
        connection.close()
