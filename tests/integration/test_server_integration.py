import json
import logging
import time
import urllib.error
import urllib.request

import pytest

from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.web_service_manager import WebServiceManager

# Configure logging
logger = logging.getLogger(__name__)


@pytest.fixture
def test_db_path(tmp_path):
    """Fixture to provide a temporary database path."""
    return str(tmp_path / "test_server_integration.kraken")


@pytest.fixture
def setup_db(test_db_path):
    """Create a temporary database with some longform content via Service."""
    # Initialize Service (creates schema)
    db = DatabaseService(test_db_path)
    db.connect()

    # Create Event with Longform Meta
    longform_meta = {
        "default": {
            "position": 100.0,
            "heading_level": 1,
            "title_override": "Chapter One",
            "depth": 0,
        }
    }

    attributes = {"_longform": longform_meta}

    event = Event(
        name="Event 1",
        description="This is the **first** event content.",
        lore_date=100.0,
        attributes=attributes,
    )
    # Manually set ID to be deterministic for assertions
    event.id = "evt-1"

    db.insert_event(event)
    db.close()
    return test_db_path


@pytest.fixture
def free_port():
    """Get a free port on localhost."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def web_server(setup_db, free_port):
    """Fixture to start and stop the web server."""
    manager = WebServiceManager()
    manager._config.db_path = setup_db

    port = free_port
    logger.info(f"Starting server on port {port}...")
    manager.start_server(port)

    # Wait for server to start
    start_time = time.time()
    server_started = False

    # URL for health check
    health_url = f"http://127.0.0.1:{port}/health"

    while time.time() - start_time < 10:
        try:
            with urllib.request.urlopen(health_url) as response:
                if response.getcode() == 200:
                    server_started = True
                    break
        except Exception:
            time.sleep(0.1)

    if not server_started:
        manager.stop_server()
        pytest.fail(f"Server failed to start on port {port} within timeout")

    # Attach port to manager for test access
    manager._test_port = port

    yield manager

    logger.info("Stopping server...")
    manager.stop_server()
    # Wait a bit for thread to release DB
    time.sleep(0.5)


def http_get(url):
    """Helper to perform HTTP GET."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise


def test_server_endpoints(web_server):
    """Run the server verification."""
    port = web_server._test_port

    # 1. Test Health
    code, body = http_get(f"http://127.0.0.1:{port}/health")
    logger.info(f"Health: {code} {body}")
    assert code == 200
    assert json.loads(body)["status"] == "ok"

    # 2. Test Longform API (now includes lore_date/lore_duration)
    code, body = http_get(f"http://127.0.0.1:{port}/api/longform")
    assert code == 200
    data = json.loads(body)
    assert data["title"] == "default"
    assert len(data["sections"]) == 1
    section = data["sections"][0]
    assert section["id"] == "evt-1"
    assert "first" in section["html"]
    # Event section exposes lore fields for client-side date rendering
    assert section["lore_date"] == 100.0
    assert "lore_duration" in section

    # 3. Test TOC API
    code, body = http_get(f"http://127.0.0.1:{port}/api/toc")
    assert code == 200
    data = json.loads(body)
    assert len(data) == 1
    assert data[0]["title"] == "Chapter One"

    # 4. Test HTML Page
    code, body = http_get(f"http://127.0.0.1:{port}/longform")
    assert code == 200
    assert '<div id="app">' in body


def test_root_redirects_to_longform(web_server):
    """GET / should redirect to /longform."""
    port = web_server._test_port
    # Manually inspect the redirect (urllib follows by default).
    req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
    # Install a handler that does NOT follow redirects.
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

    opener = urllib.request.build_opener(NoRedirect())
    try:
        opener.open(req)
        raise AssertionError("Expected redirect")
    except urllib.error.HTTPError as e:
        assert e.code in (301, 302, 307, 308)
        assert "/longform" in e.headers.get("Location", "")


def test_api_theme_endpoint(web_server):
    """/api/theme returns active_theme and themes dict with expected keys."""
    port = web_server._test_port
    code, body = http_get(f"http://127.0.0.1:{port}/api/theme")
    assert code == 200
    data = json.loads(body)
    assert "active_theme" in data
    assert "themes" in data
    assert isinstance(data["themes"], dict)
    # Should have at least the default dark_mode theme with core color keys
    assert "dark_mode" in data["themes"]
    dark = data["themes"]["dark_mode"]
    for key in ("app_bg", "surface", "primary", "text_main", "event_main"):
        assert key in dark, f"Missing theme key: {key}"


def test_api_toc_respects_filter(web_server):
    """/api/toc accepts filter_json and returns the same filtered set as longform."""
    port = web_server._test_port
    # Filter that includes a nonexistent tag -> no results
    filter_json = json.dumps({"include": ["nonexistent_tag_xyz"]})
    import urllib.parse

    q = urllib.parse.urlencode({"filter_json": filter_json})
    code, body = http_get(f"http://127.0.0.1:{port}/api/toc?{q}")
    assert code == 200
    assert json.loads(body) == []


def test_longform_page_embeds_initial_theme(web_server):
    """The /longform HTML includes the active theme name for JS bootstrap."""
    port = web_server._test_port
    code, body = http_get(f"http://127.0.0.1:{port}/longform")
    assert code == 200
    # The template renders window.__INITIAL_THEME__ = "dark_mode" by default.
    assert "__INITIAL_THEME__" in body
    assert "dark_mode" in body


def test_wikilink_target_is_escaped():
    """Verify attribute escaping in _resolve_wikilinks — defense against injection."""
    from src.webserver.server import _resolve_wikilinks

    # Target containing a quote must not break out of the attribute
    result = _resolve_wikilinks('See [[bad"name|Label]] for details')
    assert 'data-target="bad"name"' not in result
    assert "&quot;" in result
    # Plain form also escaped
    result2 = _resolve_wikilinks('[[<script>alert(1)</script>]]')
    assert "<script>" not in result2
    assert "&lt;script&gt;" in result2
