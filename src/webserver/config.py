"""
Configuration helpers for the Longform web server.
"""

from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Configuration for the embedded web server.

    Attributes:
        host: Host address to bind to (default: 0.0.0.0 for all interfaces).
        port: Port number to listen on (default: 8000).
        db_path: Path to the database file to serve data from.
    """

    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "world.kraken"
    poll_interval_ms: int = 5000
