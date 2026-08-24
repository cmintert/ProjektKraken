"""Configuration helpers for the Longform web server."""

import re
from dataclasses import dataclass

LOCAL_ALLOWED_HOSTS = ("127.0.0.1", "localhost", "::1")


@dataclass
class ServerConfig:
    """Configuration for the embedded web server.

    Attributes:
        host: Host address to bind to (default: localhost only).
        port: Port number to listen on (default: 8000).
        db_path: Path to the database file to serve data from.
        poll_interval_ms: Reserved for future live-reload polling (unused).
        theme_name: Name of the active theme at server start (from ThemeManager).
        lan_access: Whether requests to API endpoints require an access code.
        access_code: Ephemeral eight-digit access code for LAN mode.
        allowed_hosts: Exact Host header values accepted by the server.

    """

    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "world.kraken"
    poll_interval_ms: int = 5000
    theme_name: str = "dark_mode"
    lan_access: bool = False
    access_code: str | None = None
    allowed_hosts: tuple[str, ...] = LOCAL_ALLOWED_HOSTS

    def __post_init__(self) -> None:
        """Reject incomplete or malformed LAN authentication configuration."""
        if self.lan_access and not re.fullmatch(r"\d{8}", self.access_code or ""):
            raise ValueError("LAN access requires an eight-digit access code")
        if not self.allowed_hosts or any(
            not host or "*" in host or host != host.strip().lower()
            for host in self.allowed_hosts
        ):
            raise ValueError("Allowed hosts must be explicit lowercase host names")
