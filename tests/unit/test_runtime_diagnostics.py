"""Runtime diagnostics must survive console-free Python and native failures."""

import os
import subprocess
import sys
import threading

import pytest

import launcher
from src.app.startup_check import EnvironmentCheck
from src.core import runtime_diagnostics


@pytest.fixture(autouse=True)
def restore_hooks():
    """Keep process-wide exception hooks local to each test."""
    yield
    runtime_diagnostics.shutdown_runtime_diagnostics()


def test_uncaught_python_and_thread_tracebacks_are_persisted(tmp_path, monkeypatch):
    """Both hooks write session and thread context, then delegate once."""
    delegated_python = []
    delegated_threads = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: delegated_python.append(args))
    monkeypatch.setattr(
        threading, "excepthook", lambda args: delegated_threads.append(args)
    )
    path = runtime_diagnostics.install_runtime_diagnostics(tmp_path)
    assert path is not None
    assert runtime_diagnostics.install_runtime_diagnostics(tmp_path) == path
    try:
        raise ValueError("main failure")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    def fail_in_thread():
        raise RuntimeError("worker failure")

    thread = threading.Thread(target=fail_in_thread, name="diagnostic-worker")
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()

    text = path.read_text(encoding="utf-8")
    assert "session=" in text
    assert "source=uncaught-python" in text
    assert "ValueError: main failure" in text
    assert "source=uncaught-thread:diagnostic-worker" in text
    assert "RuntimeError: worker failure" in text
    assert len(delegated_python) == 1
    assert len(delegated_threads) == 1
    state = runtime_diagnostics._state
    assert state is not None
    runtime_diagnostics.shutdown_runtime_diagnostics()
    assert state.fault_file.closed
    assert not runtime_diagnostics.faulthandler.is_enabled()


def test_launcher_import_failure_is_persisted_before_application_import(
    tmp_path, monkeypatch
):
    """The source launcher opens the fault file before importing the GUI."""
    monkeypatch.setattr(sys, "argv", ["launcher.py"])
    monkeypatch.setattr(launcher, "check_environment", lambda: EnvironmentCheck(()))
    monkeypatch.setattr(
        launcher, "report_unhandled_startup_exception", lambda exc: None
    )
    monkeypatch.setattr(
        launcher,
        "install_runtime_diagnostics",
        lambda: runtime_diagnostics.install_runtime_diagnostics(tmp_path),
    )
    monkeypatch.setitem(sys.modules, "src.app.entry", None)
    assert launcher.run() == 1
    diagnostic = next(tmp_path.glob("faults.*.log")).read_text(encoding="utf-8")
    assert "source=startup" in diagnostic
    assert "src.app.entry" in diagnostic


def test_diagnostic_write_failure_still_delegates_original_exception(
    tmp_path, monkeypatch
):
    """A failed diagnostic write cannot hide the original exception."""
    delegated = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: delegated.append(args))
    runtime_diagnostics.install_runtime_diagnostics(tmp_path)

    def fail_write(_message):
        raise OSError("disk full")

    monkeypatch.setattr(runtime_diagnostics, "_write_direct", fail_write)
    try:
        raise LookupError("original failure")
    except LookupError:
        sys.excepthook(*sys.exc_info())
    assert len(delegated) == 1
    assert str(delegated[0][1]) == "original failure"


def test_qt_callback_and_warning_are_persisted_once_in_real_event_loop(tmp_path):
    """Exercise the PySide callback boundary outside pytest's Qt hook."""
    script = """
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer, qCritical, qWarning
from PySide6.QtWidgets import QApplication
from src.core.runtime_diagnostics import (
    install_qt_message_handler, install_runtime_diagnostics,
    shutdown_runtime_diagnostics,
)
sys.stderr = None
install_runtime_diagnostics(Path(os.environ['KRAKEN_DIAGNOSTIC_TEST_DIR']))
install_qt_message_handler()
app = QApplication([])
def fail():
    qWarning('qt warning probe')
    qCritical('qt critical probe')
    raise RuntimeError('qt callback failure')
QTimer.singleShot(0, fail)
QTimer.singleShot(100, app.quit)
app.exec()
shutdown_runtime_diagnostics()
"""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["KRAKEN_DIAGNOSTIC_TEST_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    diagnostic = next(tmp_path.glob("faults.*.log")).read_text(encoding="utf-8")
    assert diagnostic.count("RuntimeError: qt callback failure") == 1
    assert "severity=QtWarningMsg" in diagnostic
    assert "severity=QtCriticalMsg" in diagnostic
    assert "message=qt warning probe" in diagnostic
    assert "message=qt critical probe" in diagnostic
    assert "category=" in diagnostic
    assert "file=" in diagnostic


def test_native_fault_writes_persistent_traceback_in_child_process(tmp_path):
    """Crash only a child interpreter and inspect its durable fault output."""
    script = """
import faulthandler
import os
import sys
from pathlib import Path
from src.core.runtime_diagnostics import install_runtime_diagnostics
sys.stderr = None
install_runtime_diagnostics(Path(os.environ['KRAKEN_DIAGNOSTIC_TEST_DIR']))
faulthandler._sigsegv()
"""
    environment = os.environ.copy()
    environment["KRAKEN_DIAGNOSTIC_TEST_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
        check=False,
    )
    assert result.returncode != 0
    diagnostic = next(tmp_path.glob("faults.*.log")).read_text(encoding="utf-8")
    assert "Fatal Python error" in diagnostic
    assert "Current thread" in diagnostic
    assert 'File "<string>"' in diagnostic


def test_qt_fatal_message_is_persisted_before_child_aborts(tmp_path):
    """A fatal Qt message reaches the direct file sink before process death."""
    script = """
import os
import sys
from pathlib import Path
from PySide6.QtCore import qFatal
from src.core.runtime_diagnostics import (
    install_qt_message_handler, install_runtime_diagnostics,
)
sys.stderr = None
install_runtime_diagnostics(Path(os.environ['KRAKEN_DIAGNOSTIC_TEST_DIR']))
install_qt_message_handler()
qFatal('qt fatal probe')
"""
    environment = os.environ.copy()
    environment["KRAKEN_DIAGNOSTIC_TEST_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
        check=False,
    )
    assert result.returncode != 0
    diagnostic = next(tmp_path.glob("faults.*.log")).read_text(encoding="utf-8")
    assert "severity=QtFatalMsg" in diagnostic
    assert "message=qt fatal probe" in diagnostic
