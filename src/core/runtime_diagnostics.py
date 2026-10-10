"""Persistent best-effort diagnostics for uncaught Python and native failures."""

from __future__ import annotations

import atexit
import faulthandler
import os
import sys
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, BinaryIO, cast

from src.core.logging_config import get_writable_log_directory
from src.core.operation_trace import SESSION_ID

if TYPE_CHECKING:
    from PySide6.QtCore import QMessageLogContext, QtMsgType

PythonHook = Callable[
    [type[BaseException], BaseException, TracebackType | None], object
]
ThreadHook = Callable[[threading.ExceptHookArgs], object]
QtHook = Callable[..., object]


@dataclass
class _DiagnosticState:
    """Keep the fault file and the hooks it replaced alive for one session."""

    fault_file: BinaryIO
    path: Path
    session_id: str
    python_hook: PythonHook
    thread_hook: ThreadHook
    fault_enabled: bool = False
    qt_installed: bool = False
    qt_hook: QtHook | None = None


_state: _DiagnosticState | None = None
_write_lock = threading.Lock()
_delegating_thread = threading.local()
_atexit_registered = False


def _write_direct(message: str) -> None:
    """Append without logging or a buffered stream that a crash might lose."""
    state = _state
    if state is None:
        return
    data = message.encode("utf-8", errors="backslashreplace")
    with _write_lock:
        view = memoryview(data)
        while view:
            written = os.write(state.fault_file.fileno(), view)
            if written == 0:
                raise OSError("diagnostic write made no progress")
            view = view[written:]


def _header(source: str) -> str:
    """Describe a diagnostic event without depending on the logging system."""
    state = _state
    session = state.session_id if state is not None else "unknown"
    now = datetime.now(timezone.utc).isoformat()
    thread = threading.current_thread()
    return (
        f"[{now}] session={session} pid={os.getpid()} "
        f"thread={thread.name}/{thread.ident} source={source}"
    )


def _record_exception(
    source: str,
    exc_type: type[BaseException],
    value: BaseException,
    tb: TracebackType | None,
) -> None:
    """Persist a complete traceback, then let the original hook run."""
    try:
        trace = "".join(traceback.format_exception(exc_type, value, tb))
        _write_direct(f"{_header(source)}\n{trace}\n")
    except Exception:
        pass


def record_startup_exception(exc: BaseException) -> None:
    """Persist a caught startup failure that will not reach ``sys.excepthook``."""
    _record_exception("startup", type(exc), exc, exc.__traceback__)


def _python_exception_hook(
    exc_type: type[BaseException],
    value: BaseException,
    tb: TracebackType | None,
) -> None:
    """Capture uncaught main-thread and Qt callback exceptions once."""
    state = _state
    if state is None:
        sys.__excepthook__(exc_type, value, tb)
        return
    if not getattr(_delegating_thread, "active", False):
        _record_exception("uncaught-python", exc_type, value, tb)
    state.python_hook(exc_type, value, tb)


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    """Capture uncaught background-thread failures before delegating."""
    state = _state
    if state is None:
        threading.__excepthook__(args)
        return
    if args.exc_type is not None and args.exc_value is not None:
        name = args.thread.name if args.thread is not None else "unknown"
        _record_exception(
            f"uncaught-thread:{name}", args.exc_type, args.exc_value, args.exc_traceback
        )
    _delegating_thread.active = True
    try:
        state.thread_hook(args)
    finally:
        _delegating_thread.active = False


def install_runtime_diagnostics(directory: Path | None = None) -> Path | None:
    """Open a persistent fault file and install Python exception hooks."""
    global _atexit_registered, _state
    if _state is not None:
        return _state.path
    log_dir = directory if directory is not None else get_writable_log_directory()
    if log_dir is None:
        return None
    path = Path(log_dir) / f"faults.{os.getpid()}.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fault_file = path.open("ab", buffering=0)
    except OSError:
        return None

    _state = _DiagnosticState(
        fault_file=fault_file,
        path=path,
        session_id=SESSION_ID,
        python_hook=sys.excepthook,
        thread_hook=threading.excepthook,
    )
    try:
        _write_direct(f"{_header('session-start')}\n")
        faulthandler.enable(file=fault_file, all_threads=True)
        _state.fault_enabled = True
    except Exception as exc:
        try:
            _write_direct(f"{_header('fault-handler-unavailable')} {exc}\n")
        except Exception:
            pass
    sys.excepthook = _python_exception_hook
    threading.excepthook = _thread_exception_hook
    if not _atexit_registered:
        atexit.register(shutdown_runtime_diagnostics)
        _atexit_registered = True
    return path


def _qt_message_handler(
    severity: QtMsgType, context: QMessageLogContext, message: str
) -> None:
    """Persist warnings and failures with Qt's source context."""
    state = _state
    if state is None:
        return
    try:
        from PySide6.QtCore import QtMsgType

        if severity in (
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        ):
            _write_direct(
                f"{_header('qt')} severity={severity.name} "
                f"category={getattr(context, 'category', None) or '-'} "
                f"file={getattr(context, 'file', None) or '-'} "
                f"line={getattr(context, 'line', None) or 0} "
                f"function={getattr(context, 'function', None) or '-'} "
                f"message={message}\n"
            )
    except Exception:
        pass
    if state.qt_hook is not None:
        try:
            state.qt_hook(severity, context, message)
        except Exception:
            pass


def install_qt_message_handler() -> None:
    """Capture relevant Qt messages after QtCore is safe to import."""
    state = _state
    if state is None or state.qt_installed:
        return
    try:
        from PySide6.QtCore import qInstallMessageHandler

        state.qt_hook = cast(QtHook | None, qInstallMessageHandler(_qt_message_handler))
        state.qt_installed = True
    except Exception:
        pass


def shutdown_runtime_diagnostics() -> None:
    """Restore hooks and disable faulthandler before closing its file."""
    global _state
    state = _state
    if state is None:
        return
    if state.qt_installed:
        try:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(state.qt_hook)
        except Exception:
            pass
    if sys.excepthook is _python_exception_hook:
        sys.excepthook = state.python_hook
    if threading.excepthook is _thread_exception_hook:
        threading.excepthook = state.thread_hook
    if state.fault_enabled:
        try:
            faulthandler.disable()
        except Exception:
            pass
    try:
        _write_direct(f"{_header('session-end')}\n")
    except Exception:
        pass
    _state = None
    try:
        state.fault_file.close()
    except OSError:
        pass
