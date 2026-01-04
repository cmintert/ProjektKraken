import json
import logging
import os
import sys
import time
import traceback
import urllib.request

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.web_service_manager import WebServiceManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEST_DB_PATH = "test_verify_server.kraken"
PORT = 8092  # Use different port to avoid conflict if previous didn't release


def setup_test_db():
    """Create a temporary database with some longform content via Service."""
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

    # Initialize Service (creates schema)
    db = DatabaseService(TEST_DB_PATH)
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


def http_get(url):
    try:
        with urllib.request.urlopen(url) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise


def verify_server():
    """Run the server verification."""
    try:
        setup_test_db()
    except Exception:
        logger.error("DB Setup failed")
        traceback.print_exc()
        return

    # Start web server
    manager = WebServiceManager()
    manager._config.db_path = TEST_DB_PATH

    logger.info(f"Starting server on port {PORT}...")
    manager.start_server(PORT)

    # Wait for start
    time.sleep(3)

    try:
        # 1. Test Health
        code, body = http_get(f"http://127.0.0.1:{PORT}/health")
        logger.info(f"Health: {code} {body}")
        assert code == 200
        assert json.loads(body)["status"] == "ok"
        logger.info("[PASS] Health Check")

        # 2. Test Longform API
        code, body = http_get(f"http://127.0.0.1:{PORT}/api/longform")
        if code != 200:
            logger.error(f"Longform API Error: {body}")
        assert code == 200
        data = json.loads(body)
        assert data["title"] == "default"
        assert len(data["sections"]) == 1
        assert data["sections"][0]["id"] == "evt-1"
        assert "first" in data["sections"][0]["html"]
        logger.info("[PASS] Longform API")

        # 3. Test TOC API
        code, body = http_get(f"http://127.0.0.1:{PORT}/api/toc")
        assert code == 200
        data = json.loads(body)
        assert len(data) == 1
        assert data[0]["title"] == "Chapter One"
        logger.info("[PASS] TOC API")

        # 4. Test HTML Page
        code, body = http_get(f"http://127.0.0.1:{PORT}/longform")
        assert code == 200
        assert '<div id="app">' in body
        logger.info("[PASS] HTML Page Serve")

    except Exception as e:
        logger.error(f"Verification FAILED: {e}")
        traceback.print_exc()
        raise
    finally:
        logger.info("Stopping server...")
        manager.stop_server()
        # Wait a bit for thread to release DB
        time.sleep(1)
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except OSError:
                pass


if __name__ == "__main__":
    verify_server()
