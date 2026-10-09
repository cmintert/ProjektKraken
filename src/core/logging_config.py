"""Logging Configuration Module.

This module provides centralized logging configuration for the application, including
rotating file handlers and console output.
"""

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from src.core.paths import get_log_directory, get_user_data_path

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
ROTATION_RETRY_SECONDS = 30.0
_owned_handlers: dict[logging.Logger, list[logging.Handler]] = {}


def _process_filename(filename: str) -> str:
    """Give each process its own rotation set without cross-process file locks."""
    stem, extension = os.path.splitext(filename)
    return f"{stem}.{os.getpid()}{extension}"


def _diagnostic(message: str, path: str | None = None) -> None:
    """Report a logging failure directly, without entering logging again."""
    if path is not None:
        try:
            Path(path).with_suffix(".logging-error.txt").write_text(
                message + "\n", encoding="utf-8"
            )
        except OSError:
            pass
    stream = sys.stderr
    if stream is not None:
        try:
            stream.write(message + "\n")
        except Exception:
            pass


def _replace_owned_handlers(logger: logging.Logger) -> None:
    """Detach and close only handlers installed by this module."""
    for handler in _owned_handlers.pop(logger, []):
        logger.removeHandler(handler)
        handler.close()


def _add_owned_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    logger.addHandler(handler)
    _owned_handlers.setdefault(logger, []).append(handler)


def get_writable_log_directory() -> str | None:
    """Prefer portable logs, then the user data directory; never use cwd."""
    for candidate in (_resolve_log_directory, lambda: get_user_data_path("logs")):
        try:
            path = candidate()
            os.makedirs(path, exist_ok=True)
            probe = Path(path) / f".logging-write-test-{os.getpid()}"
            with probe.open("w", encoding="utf-8"):
                pass
            probe.unlink()
            return path
        except OSError as exc:
            _diagnostic(f"ProjektKraken log directory unavailable: {exc}")
    return None


def _resolve_log_directory() -> str:
    """Return the configured log directory or the portable default."""
    if LOG_DIR is not None:
        os.makedirs(LOG_DIR, exist_ok=True)
        return LOG_DIR
    return str(get_log_directory())


class SafeRotatingFileHandler(RotatingFileHandler):
    """Suspend writes after I/O failure and retry without growing a locked file."""

    def __init__(
        self,
        filename: str,
        maxBytes: int,
        backupCount: int,
        encoding: str,
        delay: bool,
    ) -> None:
        """Initialize a bounded rotating file with an independent retry clock."""
        super().__init__(
            filename,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
        )
        self._retry_at = 0.0

    def emit(self, record: logging.LogRecord) -> None:
        """Write only when rotation succeeds; logging errors stay best effort."""
        if time.monotonic() < self._retry_at:
            return
        try:
            if self.shouldRollover(record):
                self.doRollover()
            if self.stream is None:
                self.stream = self._open()
            self.stream.write(self.format(record) + self.terminator)
            self.flush()
            self._retry_at = 0.0
        except Exception as exc:
            self._retry_at = time.monotonic() + ROTATION_RETRY_SECONDS
            _diagnostic(
                f"ProjektKraken logging suspended for {ROTATION_RETRY_SECONDS:g}s "
                f"at {self.baseFilename}: {type(exc).__name__}: {exc}",
                self.baseFilename,
            )


def setup_logging(debug_mode: bool = False, log_to_console: bool = True) -> None:
    """Configures the root logger with a rotating file handler and optional console
    handler.

    This function should be called once at the application startup.

    Args:
        debug_mode (bool): If True, sets level to DEBUG. Defaults to False (INFO).
        log_to_console (bool): If True, adds a StreamHandler. Defaults to True.

    """
    log_dir = get_writable_log_directory()
    root_logger = logging.getLogger()
    _replace_owned_handlers(root_logger)

    level = logging.DEBUG if debug_mode else logging.INFO
    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    if log_dir is not None:
        log_path = os.path.join(log_dir, _process_filename(LOG_FILENAME))
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
            _add_owned_handler(root_logger, file_handler)
        except OSError as exc:
            _diagnostic(f"ProjektKraken file logging unavailable: {exc}")

    if log_to_console:
        if sys.stderr is not None:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(level)
            _add_owned_handler(root_logger, console_handler)

    # Force DEBUG for UnifiedList to troubleshoot focus issue
    logging.getLogger("src.gui.widgets.unified_list").setLevel(logging.DEBUG)

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
    events to a process-specific audit file. The logger does **not**
    propagate to the root logger so audit entries stay in their own file.
    """
    audit_logger = logging.getLogger("ai_audit")

    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't spam the main log
    log_dir = get_writable_log_directory()
    if log_dir is None:
        _replace_owned_handlers(audit_logger)
        return
    audit_path = os.path.join(log_dir, _process_filename(AUDIT_LOG_FILENAME))
    owned = _owned_handlers.get(audit_logger, [])
    if (
        len(owned) == 1
        and owned[0] in audit_logger.handlers
        and getattr(owned[0], "baseFilename", None) == audit_path
    ):
        return
    _replace_owned_handlers(audit_logger)

    try:
        _add_owned_handler(audit_logger, _make_audit_handler(audit_path))
    except OSError as exc:
        _diagnostic(f"Could not set up AI audit logging: {exc}")


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

    if any(
        handler in audit_logger.handlers
        for handler in _owned_handlers.get(audit_logger, [])
    ):
        return audit_logger

    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    try:
        os.makedirs(os.path.dirname(audit_path), exist_ok=True)
        _add_owned_handler(audit_logger, _make_audit_handler(audit_path))
    except OSError as e:
        _diagnostic(f"Could not set up per-world AI audit logging at {audit_path}: {e}")

    return audit_logger


def get_world_audit_log_path(db_path: Optional[str]) -> Optional[str]:
    """Return the per-world audit log path derived from a world database path.

    Args:
        db_path: Absolute path to the world ``.kraken`` database file, or
            ``None`` / ``":memory:"`` for in-memory databases.

    Returns:
        Optional[str]: Absolute path to a process-specific audit file in the same
        directory as the database, or ``None`` when no persistent path is
        available.

    """
    if db_path and db_path != ":memory:":
        return os.path.join(
            os.path.dirname(db_path), _process_filename(AUDIT_LOG_FILENAME)
        )
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
    for logger in list(_owned_handlers):
        _replace_owned_handlers(logger)
    logging.shutdown()
