"""Capture native editor destruction through the end of an isolated process."""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("content", ["empty", "populated", "history"])
@pytest.mark.parametrize("disposal", ["widget", "application", "process"])
def test_editor_shutdown_has_no_paint_device_warnings(tmp_path, content, disposal):
    script = r"""
import sys
import shiboken6
from src.app import entry
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from src.gui.widgets.wiki_text_edit import WikiTextEditView

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, sys.argv[3])
app = QApplication([])
view = WikiTextEditView()
if sys.argv[1] != "empty":
    view.set_wiki_text("A paragraph of text.\n\n" * 20)
if sys.argv[1] == "history":
    initial = view.get_wiki_text()
    cursor = view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    view.setTextCursor(cursor)
    view.insertPlainText(" rich")
    view.toggle_view_mode()
    view.insertPlainText(" source")
    view.toggle_view_mode()
    edited = view.get_wiki_text()
    view.undo()
    view.undo()
    assert view.get_wiki_text() == initial
    view.redo()
    view.redo()
    assert view.get_wiki_text() == edited
view.show()
QTimer.singleShot(0, view.close)
app.exec()
if sys.argv[2] == "widget":
    shiboken6.delete(view)
elif sys.argv[2] == "application":
    order = []
    def logging_stopped():
        assert not shiboken6.isValid(view)
        assert not shiboken6.isValid(app)
        order.append("logging")
    def diagnostics_stopped():
        assert order == ["logging"]
        order.append("diagnostics")
    entry.shutdown_logging = logging_stopped
    entry.shutdown_runtime_diagnostics = diagnostics_stopped
    entry.cleanup_app(app)
    assert order == ["logging", "diagnostics"]
"""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = os.environ.get(
        "KRAKEN_TEST_QPA_PLATFORM", "offscreen"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, content, disposal, str(tmp_path)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QPaintDevice::metrics" not in result.stderr
    assert "Internal C++ object" not in result.stderr
