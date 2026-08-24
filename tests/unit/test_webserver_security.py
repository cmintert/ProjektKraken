"""Security regression tests for embedded longform publishing."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService
from src.services.longform_builder import insert_or_update_longform_meta
from src.webserver.config import LOCAL_ALLOWED_HOSTS, ServerConfig
from src.webserver.server import (
    _CONTENT_SECURITY_POLICY,
    _AccessCodeRateLimiter,
    create_app,
)


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


def _client(config: ServerConfig) -> TestClient:
    """Create a client using the default local Host accepted by the server."""
    return TestClient(create_app(config), base_url="http://127.0.0.1")


def test_server_config_defaults_to_localhost() -> None:
    config = ServerConfig()

    assert config.host == "127.0.0.1"
    assert config.lan_access is False
    assert config.access_code is None
    assert config.allowed_hosts == LOCAL_ALLOWED_HOSTS


@pytest.mark.parametrize("code", [None, "1234567", "123456789", "abcdefgh"])
def test_lan_config_requires_eight_digit_code(code: str | None) -> None:
    with pytest.raises(ValueError, match="eight-digit"):
        ServerConfig(lan_access=True, access_code=code)


@pytest.mark.ci_fast
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost:8000", "[::1]:8000"])
def test_loopback_host_headers_are_accepted(host: str, published_db_path: str) -> None:
    """The embedded viewer remains reachable through every supported loopback URL."""
    response = _client(ServerConfig(db_path=published_db_path)).get(
        "/health", headers={"Host": host}
    )

    assert response.status_code == 200


@pytest.mark.ci_fast
@pytest.mark.parametrize("path", ["/api/longform", "/longform", "/static/app.js"])
def test_untrusted_host_is_rejected_before_server_routes(
    published_db_path: str, path: str
) -> None:
    """DNS-rebinding Host headers cannot reach viewer, static, or API routes."""
    app = create_app(ServerConfig(db_path=published_db_path))
    client = TestClient(app, base_url="http://127.0.0.1")

    with patch("src.webserver.server.get_db_service") as get_db_service:
        response = client.get(path, headers={"Host": "attacker.test"})

    assert response.status_code == 400
    assert get_db_service.call_count == 0


@pytest.mark.ci_fast
def test_lan_mode_accepts_displayed_ip_and_rejects_hostnames(
    published_db_path: str,
) -> None:
    """LAN sharing admits only its displayed address and loopback aliases."""
    lan_ip = "192.168.1.20"
    config = ServerConfig(
        host="0.0.0.0",
        db_path=published_db_path,
        lan_access=True,
        access_code="01234567",
        allowed_hosts=(*LOCAL_ALLOWED_HOSTS, lan_ip),
    )
    client = _client(config)

    accepted = client.get(
        "/api/longform",
        headers={
            "Host": f"{lan_ip}:8000",
            "Authorization": "Bearer 01234567",
        },
    )
    rejected = client.get(
        "/api/longform",
        headers={
            "Host": "kraken.local",
            "Authorization": "Bearer 01234567",
        },
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 400


def test_local_mode_does_not_require_authentication(published_db_path: str) -> None:
    client = _client(ServerConfig(db_path=published_db_path))

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
    client = _client(config)

    missing = client.get(path)
    wrong = client.get(path, headers={"Authorization": "Bearer 76543210"})
    valid = client.get(path, headers={"Authorization": "Bearer 01234567"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200
    for response in (missing, wrong, valid):
        assert response.headers["Content-Security-Policy"] == (
            _CONTENT_SECURITY_POLICY
        )


def test_lan_viewer_shell_and_health_remain_public(published_db_path: str) -> None:
    config = ServerConfig(
        host="0.0.0.0",
        db_path=published_db_path,
        lan_access=True,
        access_code="01234567",
    )
    client = _client(config)

    viewer = client.get("/longform")
    assert viewer.status_code == 200
    assert "LAN access required" in viewer.text
    assert 'data-lan-access="true"' in viewer.text
    assert "window.__LAN_ACCESS__" not in viewer.text
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
    client = _client(config)

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
    assert limited.headers["Content-Security-Policy"] == _CONTENT_SECURITY_POLICY


def test_rate_limiter_has_a_global_failure_bound() -> None:
    limiter = _AccessCodeRateLimiter()

    for index in range(29):
        assert limiter.record_failure(f"client-{index}") is None

    assert limiter.record_failure("client-29") is not None


def test_http_get_does_not_index_missing_items(published_db_path: str) -> None:
    before = _event_attributes(published_db_path, "unindexed")
    client = _client(ServerConfig(db_path=published_db_path))

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
    client = _client(ServerConfig(db_path=published_db_path))

    response = client.get("/api/longform", params={"doc_id": doc_id})

    assert response.status_code == 422


def test_maximum_length_doc_id_is_accepted(published_db_path: str) -> None:
    client = _client(ServerConfig(db_path=published_db_path))

    response = client.get("/api/longform", params={"doc_id": "a" * 64})

    assert response.status_code == 200


def test_markdown_and_json_imports_are_sanitized_when_published(tmp_path) -> None:
    path = str(tmp_path / "imported.kraken")
    service = DatabaseService(path)
    service.connect()
    importer = ImportService(service)

    markdown_result = importer.import_markdown(
        """---
uid: markdown-hostile
title: '<img src=x onerror="globalThis.__titleXss=true">Markdown title'
type: note
---
# Description

<script>globalThis.__bodyXss = true</script>
<img src="https://attacker.invalid/markdown" onerror="alert(1)">
**Markdown formatting** and [[json-hostile|JSON entry]].
""",
        {"filename": "hostile.md"},
    )
    json_result = importer.import_batch(
        {
            "entities": [
                {
                    "id": "json-hostile",
                    "name": "JSON entry",
                    "type": "note",
                    "description": (
                        '<svg><script>alert(1)</script></svg><a '
                        'href="java&#115;cript:alert(2)" data-any="x">bad</a> '
                        "[Safe](https://example.com)"
                    ),
                }
            ],
            "events": [],
            "relations": [],
        },
        {"source_name": "security-test"},
    )
    assert markdown_result.success
    assert json_result.success
    assert service._connection is not None
    insert_or_update_longform_meta(
        service._connection, "entities", "markdown-hostile", position=100.0
    )
    insert_or_update_longform_meta(
        service._connection, "entities", "json-hostile", position=200.0
    )
    service.close()

    response = _client(ServerConfig(db_path=path)).get("/api/longform")

    assert response.status_code == 200
    sections = {section["id"]: section for section in response.json()["sections"]}
    combined_html = "".join(section["html"] for section in sections.values())
    lowered = combined_html.lower()
    for forbidden in (
        "<script",
        "<img",
        "<svg",
        "onerror",
        "javascript:",
        "data-any",
        "attacker.invalid",
    ):
        assert forbidden not in lowered
    assert "<strong>Markdown formatting</strong>" in sections["markdown-hostile"][
        "html"
    ]
    assert (
        '<a class="wikilink" data-target="json-hostile">JSON entry</a>'
        in sections["markdown-hostile"]["html"]
    )
    assert '<a href="https://example.com">Safe</a>' in sections["json-hostile"][
        "html"
    ]


@pytest.mark.parametrize(
    ("path", "follow_redirects"),
    [
        ("/", False),
        ("/longform", True),
        ("/api/longform", True),
        ("/static/app.js", True),
        ("/missing", True),
        ("/api/longform?doc_id=bad/id", True),
    ],
)
def test_security_headers_cover_success_and_error_responses(
    published_db_path: str, path: str, follow_redirects: bool
) -> None:
    client = _client(ServerConfig(db_path=published_db_path))

    response = client.get(path, follow_redirects=follow_redirects)

    assert response.headers["Content-Security-Policy"] == _CONTENT_SECURITY_POLICY
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_security_headers_cover_unhandled_server_errors(
    published_db_path: str,
) -> None:
    app = create_app(ServerConfig(db_path=published_db_path))
    client = TestClient(
        app,
        base_url="http://127.0.0.1",
        raise_server_exceptions=False,
    )

    with patch("src.webserver.server.get_db_service", side_effect=RuntimeError("boom")):
        response = client.get("/api/longform")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["Content-Security-Policy"] == _CONTENT_SECURITY_POLICY
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_viewer_has_no_live_dom_html_sinks() -> None:
    script_path = Path(__file__).parents[2] / "src" / "webserver" / "static" / "app.js"
    source = script_path.read_text(encoding="utf-8")

    for forbidden_sink in (
        ".innerHTML",
        ".outerHTML",
        "insertAdjacentHTML",
        "createContextualFragment",
    ):
        assert forbidden_sink not in source
    assert "tocLink.textContent = titleText" in source


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
