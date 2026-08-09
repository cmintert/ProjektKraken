"""Logging Configuration Module.

This module provides centralized logging configuration for the application, including
rotating file handlers and console output.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.core.paths import get_log_directory

# Configuration
# Override hook retained for tests and specialized embeddings. Normal launches resolve
# the portable project/executable log directory through ``get_log_directory``.
LOG_DIR: str | None = None
LOG_FILENAME = "kraken.log"
AUDIT_LOG_FILENAME = "ai_audit_log.jsonl"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
AUDIT_LOG_FORMAT = "%(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_log_directory() -> str:
    """Return the configured log directory or the portable default."""
    if LOG_DIR is not None:
        os.makedirs(LOG_DIR, exist_ok=True)
        return LOG_DIR
    return str(get_log_directory())


class SafeRotatingFileHandler(RotatingFileHandler):
    """A RotatingFileHandler that handles Windows file locking errors gracefully.

    On Windows, log rotation can fail with PermissionError if the file is still in use
    by another process or handler. This handler catches those errors and continues
    logging without crashing.
    """

    def doRollover(self) -> None:
        """Perform log file rotation, catching Windows file locking errors.

        If rotation fails due to file locking (common on Windows), the handler continues
        using the current log file instead of crashing.
        """
        try:
            super().doRollover()
        except PermissionError:
            # On Windows, file may still be locked by another process
            # Just continue with the current file
            if sys.platform != "win32":
                raise
            # On Windows, silently skip rotation - will retry next opportunity


def setup_logging(debug_mode: bool = False, log_to_console: bool = True) -> None:
    """Configures the root logger with a rotating file handler and optional console
    handler.

    This function should be called once at the application startup.

    Args:
        debug_mode (bool): If True, sets level to DEBUG. Defaults to False (INFO).
        log_to_console (bool): If True, adds a StreamHandler. Defaults to True.

    """
    # 1. Create Log Directory
    try:
        log_dir = _resolve_log_directory()
    except OSError as e:
        # Fall back to the current directory if the portable log directory is not
        # writable. The console message remains visible in source launches.
        print(f"Failed to create log directory: {e}. Logging to current directory.")
        log_path = LOG_FILENAME
    else:
        log_path = os.path.join(log_dir, LOG_FILENAME)

    # 2. Get Root Logger
    root_logger = logging.getLogger()

    # Remove existing handlers to avoid duplicates if called multiple times
    if root_logger.handlers:
        root_logger.handlers.clear()

    level = logging.DEBUG if debug_mode else logging.INFO
    root_logger.setLevel(level)

    # 3. Formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 4. File Handler (Safe Rotating - handles Windows file locking)
    try:
        file_handler = SafeRotatingFileHandler(
            log_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
            delay=False,
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    except OSError as e:
        print(f"CRITICAL: Could not set up file logging: {e}")

    # 5. Console Handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    # 6. Initial Log
    # logging.info("=" * 60)
    # logging.info(f"Project Kraken Session Started at {datetime.now().isoformat()}")
    # logging.info("=" * 60)

    # Force DEBUG for UnifiedList to troubleshoot focus issue
    logging.getLogger("src.gui.widgets.unified_list").setLevel(logging.DEBUG)

    # 7. Set up AI Audit Logger (separate file)
    setup_audit_logging()


def _make_audit_handler(path: str) -> SafeRotatingFileHandler:
    """Create a rotating file handler for an audit log at *path*.

    Args:
        path: Absolute path to the audit log file.

    Returns:
        SafeRotatingFileHandler: Configured handler (delay=True so file is not
        created until the first write).

    Raises:
        OSError: If the handler cannot be created.

    """
    handler = SafeRotatingFileHandler(
        path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    formatter = logging.Formatter(AUDIT_LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    return handler


def setup_audit_logging() -> None:
    """Configure the dedicated AI audit logger.

    Creates a separate rotating file handler that writes structured AI audit
    events to ``logs/ai_audit_log.jsonl``. The logger does **not**
    propagate to the root logger so audit entries stay in their own file.
    """
    audit_logger = logging.getLogger("ai_audit")

    # Avoid adding duplicate handlers on repeat calls
    if audit_logger.handlers:
        return

    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't spam the main log

    try:
        audit_path = os.path.join(_resolve_log_directory(), AUDIT_LOG_FILENAME)
    except OSError:
        audit_path = AUDIT_LOG_FILENAME

    try:
        audit_logger.addHandler(_make_audit_handler(audit_path))
    except OSError as e:
        logging.getLogger(__name__).warning(f"Could not set up AI audit logging: {e}")


def get_audit_logger() -> logging.Logger:
    """Return the dedicated AI audit logger.

    Returns:
        logging.Logger: The ``ai_audit`` logger instance.

    """
    return logging.getLogger("ai_audit")


def get_audit_logger_for_path(audit_path: str) -> logging.Logger:
    """Return a per-world AI audit logger writing to ``audit_path``.

    Creates a ``SafeRotatingFileHandler`` for the given path on first call
    and reuses the same logger on subsequent calls (identified by path).

    Args:
        audit_path: Absolute path to the world-local audit log file.

    Returns:
        logging.Logger: Logger that writes exclusively to ``audit_path``.

    """
    logger_name = f"ai_audit:{audit_path}"
    audit_logger = logging.getLogger(logger_name)

    # Avoid duplicate handlers on repeated calls
    if audit_logger.handlers:
        return audit_logger

    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    try:
        os.makedirs(os.path.dirname(audit_path), exist_ok=True)
        audit_logger.addHandler(_make_audit_handler(audit_path))
    except OSError as e:
        logging.getLogger(__name__).warning(
            f"Could not set up per-world AI audit logging at {audit_path}: {e}"
        )

    return audit_logger


def get_world_audit_log_path(db_path: Optional[str]) -> Optional[str]:
    """Return the per-world audit log path derived from a world database path.

    Args:
        db_path: Absolute path to the world ``.kraken`` database file, or
            ``None`` / ``":memory:"`` for in-memory databases.

    Returns:
        Optional[str]: Absolute path to ``ai_audit_log.jsonl`` in the same
        directory as the database, or ``None`` when no persistent path is
        available.

    """
    if db_path and db_path != ":memory:":
        return os.path.join(os.path.dirname(db_path), AUDIT_LOG_FILENAME)
    return None


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger with the given name.

    Args:
        name (str): The name of the logger (usually __name__).

    Returns:
        logging.Logger: The logger instance.

    """
    return logging.getLogger(name)


def shutdown_logging() -> None:
    """Explicitly closes all logging handlers to release file locks."""
    logging.shutdown()
