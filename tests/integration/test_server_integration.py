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

    # 2. Test Longform API
    code, body = http_get(f"http://127.0.0.1:{port}/api/longform")
    assert code == 200
    data = json.loads(body)
    assert data["title"] == "default"
    assert len(data["sections"]) == 1
    assert data["sections"][0]["id"] == "evt-1"
    assert "first" in data["sections"][0]["html"]

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
