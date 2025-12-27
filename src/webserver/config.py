"""
Configuration helpers for the Longform web server.
"""

from dataclasses import dataclass


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "world.kraken"
    poll_interval_ms: int = 5000
