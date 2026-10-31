"""Exercise the real entry-point theme bootstrap without opening a user's world."""

import os
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.ci_fast, pytest.mark.smoke]


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
