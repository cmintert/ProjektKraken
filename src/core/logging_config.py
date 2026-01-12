"""
Logging Configuration Module.

This module provides centralized logging configuration for the application,
including rotating file handlers and console output.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Configuration
LOG_DIR = "logs"
LOG_FILENAME = "kraken.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that handles Windows file locking errors gracefully.

    On Windows, log rotation can fail with PermissionError if the file is still
    in use by another process or handler. This handler catches those errors
    and continues logging without crashing.
    """

    def doRollover(self) -> None:
        """
        Perform log file rotation, catching Windows file locking errors.

        If rotation fails due to file locking (common on Windows), the handler
        continues using the current log file instead of crashing.
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
    """
    Configures the root logger with a rotating file handler
    and optional console handler.

    This function should be called once at the application startup.

    Args:
        debug_mode (bool): If True, sets level to DEBUG. Defaults to False (INFO).
        log_to_console (bool): If True, adds a StreamHandler. Defaults to True.
    """
    # 1. Create Log Directory
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError as e:
        # Fallback to current directory if we can't create 'logs' (e.g. permissions)
        print(f"Failed to create log directory: {e}. Logging to current directory.")
        log_path = LOG_FILENAME
    else:
        log_path = os.path.join(LOG_DIR, LOG_FILENAME)

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
    logging.info("=" * 60)
    logging.info(f"Project Kraken Session Started at {datetime.now().isoformat()}")
    logging.info("=" * 60)

    # Force DEBUG for UnifiedList to troubleshoot focus issue
    logging.getLogger("src.gui.widgets.unified_list").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger with the given name.

    Args:
        name (str): The name of the logger (usually __name__).

    Returns:
        logging.Logger: The logger instance.
    """
    return logging.getLogger(name)


def shutdown_logging() -> None:
    """
    Explicitly closes all logging handlers to release file locks.
    """
    logging.shutdown()
