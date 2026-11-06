"""Exercise the real entry-point theme bootstrap without opening a user's world."""

import os
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.ci_fast, pytest.mark.smoke]


@pytest.mark.real_qt_invoke
def test_real_window_startup_waits_for_database_settings(tmp_path):
    """Start the actual shell without touching the creator's settings or worlds."""
    source = r"""
import sys
from pathlib import Path
from scripts.gui_probe_settings import install_probe_settings

root = Path(sys.argv[1])
install_probe_settings(str(root / "settings"))
import src.core.paths as paths
paths.get_worlds_dir = lambda: root / "worlds"
paths.get_user_data_path = lambda filename="": str(root / "data" / filename)
(root / "data").mkdir(parents=True, exist_ok=True)

from src.app import entry  # Install the actual OpenGL sharing/bootstrap policy.
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from src.app.main_window import MainWindow

app = QApplication([])
window = MainWindow()

def ready(success):
    print("STARTUP_COMPLETED", success, flush=True)
    QTimer.singleShot(100, window.close)

window.startup_completed.connect(ready)
window.show()
QTimer.singleShot(20000, window.close)
raise SystemExit(app.exec())
"""
    result = subprocess.run(
        [sys.executable, "-c", source, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=35,
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
            "QT_OPENGL": "software",
            "QSG_RHI_BACKEND": "software",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STARTUP_COMPLETED True" in result.stdout
    assert "World settings snapshot failed" not in result.stderr


def test_real_entry_theme_bootstrap_in_fresh_process():
    source = """
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.gui_probe_settings import install_probe_settings

with tempfile.TemporaryDirectory(prefix='kraken-startup-theme-') as directory:
    install_probe_settings(directory)
    from src.core import logging_config
    logging_config.LOG_DIR = str(Path(directory) / 'logs')
    from src.app import entry
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtWidgets import QApplication, QMainWindow

    class NoWorldWindow(QMainWindow):
        startup_completed = Signal(bool)

        def show(self):
            super().show()
            QTimer.singleShot(0, QApplication.instance().quit)

    # Only replace the world-owning window. The real QApplication, stylesheet,
    # visibility runtime, native-dialog filter and splash all install normally.
    with patch('src.app.main_window.MainWindow', NoWorldWindow), \\
         patch('src.app.startup_check.report_unhandled_startup_exception'):
        sys.argv = ['kraken-theme-startup-test']
        entry.main()
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Entering Event Loop" in result.stdout + result.stderr
