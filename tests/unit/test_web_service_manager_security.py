"""Security behavior for local and LAN web-service startup."""

import logging
from unittest.mock import patch

from src.services.web_service_manager import WebServiceManager


def test_start_server_uses_localhost_by_default(qtbot) -> None:
    manager = WebServiceManager()
    statuses: list[tuple[bool, str]] = []
    manager.status_changed.connect(lambda running, url: statuses.append((running, url)))

    with patch("src.services.web_service_manager.WebServerThread") as thread_class:
        manager.start_server(port=8123, db_path="world.kraken")

    config = thread_class.call_args.args[0]
    assert config.host == "127.0.0.1"
    assert config.lan_access is False
    assert config.access_code is None
    assert config.allowed_hosts == ("127.0.0.1", "localhost", "::1")
    assert statuses[-1] == (True, "http://127.0.0.1:8123/longform")


def test_lan_server_generates_rotating_eight_digit_codes(qtbot, caplog) -> None:
    manager = WebServiceManager()
    caplog.set_level(logging.INFO)
    statuses: list[tuple[bool, str]] = []
    manager.status_changed.connect(lambda running, url: statuses.append((running, url)))

    with (
        patch("src.services.web_service_manager.WebServerThread") as thread_class,
        patch.object(manager, "get_local_ip", return_value="192.168.1.20"),
        patch("src.services.web_service_manager.secrets.randbelow", side_effect=[7, 8]),
    ):
        manager.start_server(
            port=8123,
            db_path="world.kraken",
            share_on_lan=True,
        )
        first_config = thread_class.call_args.args[0]
        assert first_config.host == "0.0.0.0"
        assert first_config.access_code == "00000007"
        assert manager.access_code == "00000007"
        manager.stop_server()
        assert manager.access_code is None

        manager.start_server(
            port=8123,
            db_path="world.kraken",
            share_on_lan=True,
        )
        second_config = thread_class.call_args.args[0]

    assert second_config.access_code == "00000008"
    assert second_config.allowed_hosts == (
        "127.0.0.1",
        "localhost",
        "::1",
        "192.168.1.20",
    )
    assert statuses[0] == (True, "http://192.168.1.20:8123/longform")
    assert "00000007" not in caplog.text
    assert "00000008" not in caplog.text
