"""Web Service Manager Module.

Handles the lifecycle of the embedded Uvicorn server within a QThread.
"""

import logging
import secrets
import socket
import threading
from typing import Optional

import uvicorn
from PySide6.QtCore import QObject, QThread, Signal

from src.webserver.config import ServerConfig
from src.webserver.server import create_app

logger = logging.getLogger(__name__)

_ADDRESS_IN_USE_ERRNOS = {98, 10048}


class WebServerThread(QThread):
    """Background thread to run the Uvicorn server."""

    error_occurred = Signal(str)

    def __init__(self, config: ServerConfig, parent: Optional[QObject] = None) -> None:
        """Initialize the web server thread.

        Args:
            config: Server configuration (host, port, db_path).
            parent: Optional parent QObject for Qt parent-child relationship.

        """
        super().__init__(parent)
        self.config = config
        self._server: Optional[uvicorn.Server] = None
        self._stop_event = threading.Event()

    def run(self) -> None:
        """Run the server."""
        try:
            # Configure Uvicorn
            uv_config = uvicorn.Config(
                create_app(self.config),
                host=self.config.host,
                port=self.config.port,
                log_level="info",
                loop="asyncio",
            )

            # Create server instance
            self._server = uvicorn.Server(uv_config)

            # Allow clean shutdown from other threads
            # Uvicorn's server.run() handles signals, but in a thread we need to trigger
            # it manually. We override 'install_signal_handlers' to False to prevent
            # it interfering with main thread.
            uv_config.install_signal_handlers = False  # type: ignore

            logger.info("Starting Web Server Thread...")
            self._server.run()
            logger.info("Web Server Thread stopped.")

        except OSError as e:
            if e.errno in _ADDRESS_IN_USE_ERRNOS:
                self.error_occurred.emit(f"Port {self.config.port} is already in use.")
            else:
                self.error_occurred.emit(str(e))
        except Exception as e:
            logger.error(f"Web server error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def stop(self) -> None:
        """Request the server to stop."""
        if self._server:
            self._server.should_exit = True
            self.wait()  # Wait for thread to finish


class WebServiceManager(QObject):
    """Manager for the embedded web server.

    Provides methods to start/stop coverage and signals for UI updates.
    """

    status_changed = Signal(bool, str)  # is_running, message/url
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Initialize the web service manager.

        Args:
            parent: Optional parent QObject for Qt parent-child relationship.

        """
        super().__init__(parent)
        self._thread: Optional[WebServerThread] = None
        self._config = ServerConfig()  # Default config

    @property
    def is_running(self) -> bool:
        """Check if the web server is currently running.

        Returns:
            True if server thread is active and running, False otherwise.

        """
        return self._thread is not None and self._thread.isRunning()

    @property
    def is_lan_shared(self) -> bool:
        """Return whether the active server is accepting authenticated LAN access."""
        return self._thread is not None and self._config.lan_access

    @property
    def access_code(self) -> Optional[str]:
        """Return the active ephemeral LAN access code, if one exists."""
        return self._config.access_code if self.is_lan_shared else None

    def get_local_ip(self) -> str:
        """Get the local IP address for LAN access."""
        try:
            # Connect to an external server (doesn't actually send data)
            # to get the route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            # Network unavailable or other error - use localhost
            return "127.0.0.1"

    def start_server(
        self,
        port: int = 8000,
        db_path: Optional[str] = None,
        *,
        share_on_lan: bool = False,
    ) -> None:
        """Start a localhost-only server or an authenticated LAN server."""
        if self.is_running:
            return

        target_db_path = db_path or self._config.db_path

        # Capture active theme from Qt main thread before handing off to the
        # background uvicorn thread (ThemeManager is a Qt singleton).
        try:
            from src.core.theme_manager import ThemeManager

            theme_name = ThemeManager().current_theme_name
        except Exception:
            theme_name = "dark_mode"

        access_code = (
            f"{secrets.randbelow(100_000_000):08d}" if share_on_lan else None
        )
        self._config = ServerConfig(
            host="0.0.0.0" if share_on_lan else "127.0.0.1",
            port=port,
            db_path=target_db_path,
            theme_name=theme_name,
            lan_access=share_on_lan,
            access_code=access_code,
        )

        self._thread = WebServerThread(self._config)
        self._thread.error_occurred.connect(self._on_thread_error)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

        # Wait a moment to check if it crashes immediately?
        # No, async signals will handle it.

        ip = self.get_local_ip() if share_on_lan else "127.0.0.1"
        url = f"http://{ip}:{port}/longform"
        self.status_changed.emit(True, url)
        logger.info(
            "Web server started on %s:%s (%s mode)",
            self._config.host,
            port,
            "LAN" if share_on_lan else "local",
        )

    def stop_server(self) -> None:
        """Stop the web server."""
        if self._thread:
            logger.info("Stopping web server...")
            self._thread.stop()
            self._thread = None
            self._clear_access_code()
            self.status_changed.emit(False, "")

    def toggle_server(self) -> None:
        """Toggle the web server on or off.

        If server is running, stops it. If not running, starts it. Emits status_changed
        signal with the new status.
        """
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()

    def _on_thread_error(self, msg: str) -> None:
        """Handle errors from the server thread.

        Args:
            msg: The error message from the server thread.

        """
        self.error_occurred.emit(msg)
        self.stop_server()

    def _on_thread_finished(self) -> None:
        """Handle server thread completion.

        Emits status_changed signal if thread finished unexpectedly.
        """
        if self._thread:  # If finished unexpectedly
            self.status_changed.emit(False, "")
            self._thread = None
            self._clear_access_code()

    def _clear_access_code(self) -> None:
        """Discard LAN credentials while retaining the last database selection."""
        self._config = ServerConfig(
            db_path=self._config.db_path,
            port=self._config.port,
            theme_name=self._config.theme_name,
        )
