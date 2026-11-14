"""Close a composed application with an isolated real world and database worker."""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("phase", ["startup", "ready", "smoke"])
def test_application_process_closes_cleanly(tmp_path, phase):
    script = r"""
import sys
from pathlib import Path
from PySide6 import QtCore

root = Path(sys.argv[2])
NativeSettings = QtCore.QSettings
class IsolatedSettings(NativeSettings):
    def __init__(self, *args, **kwargs):
        super().__init__(str(root / "settings.ini"),
                         NativeSettings.Format.IniFormat)
QtCore.QSettings = IsolatedSettings

from src.app import entry
from src.app import main_window

phase = sys.argv[1]
RealWindow = main_window.MainWindow
class ClosingWindow(RealWindow):
    def __init__(self):
        super().__init__()
        if phase == "startup":
            QtCore.QTimer.singleShot(0, self.close)
        elif phase == "ready":
            self.startup_completed.connect(
                lambda success: QtCore.QTimer.singleShot(0, self.close))

main_window.MainWindow = ClosingWindow
sys.argv = ["kraken-shutdown-test"]
if phase == "smoke":
    sys.argv += ["--package-smoke-phase", "first-run",
                 "--package-smoke-report", str(root / "smoke-report.json")]
entry.main()
"""
    environment = os.environ.copy()
    environment.update(
        QT_QPA_PLATFORM=os.environ.get("KRAKEN_TEST_QPA_PLATFORM", "offscreen"),
        QTWEBENGINE_DISABLE_SANDBOX="1",
        QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox",
        PROJEKTKRAKEN_PERFORMANCE_WORLDS_DIR=str(tmp_path / "worlds"),
        PROJEKTKRAKEN_PERFORMANCE_LOG_DIR=str(tmp_path / "logs"),
    )
    result = subprocess.run(
        [sys.executable, "-c", script, phase, str(tmp_path)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=45,
        check=False,
    )
    expected_exit = 0
    if phase == "smoke":
        # A source checkout lacks package metadata. Verify that smoke exits with
        # its report's status after cleanup, without requiring a packaged build.
        report = json.loads((tmp_path / "smoke-report.json").read_text())
        expected_exit = 0 if report["success"] else 1
    assert result.returncode == expected_exit, result.stdout + result.stderr
    assert "QPaintDevice::metrics" not in result.stderr
    assert "QThread: Destroyed while" not in result.stderr
    assert "Traceback" not in result.stderr
    for log in (tmp_path / "logs").glob("faults.*.log"):
        assert "QPaintDevice::metrics" not in log.read_text(encoding="utf-8")
    if phase != "startup":
        assert result.stderr.index("Database connection closed in worker cleanup") < (
            result.stderr.index("Shutting down logging")
        )
