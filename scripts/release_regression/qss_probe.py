"""Reproduce existing GUI assertions with production application QSS applied."""

from __future__ import annotations

import os
import sys

from scripts.release_regression.common import ROOT


def main() -> int:
    """Bootstrap the real stylesheet, then run the requested diagnostic cases."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    import pytest
    from PySide6.QtWidgets import QApplication

    from src.core.theme_manager import ThemeManager

    application = QApplication.instance() or QApplication([])
    if not isinstance(application, QApplication):
        raise RuntimeError("Production QSS diagnostics require QApplication")
    theme = ThemeManager(str(ROOT / "themes.json"))
    application.setStyleSheet(
        theme.format_stylesheet((ROOT / "src/resources/main.qss").read_text("utf-8"))
    )
    return int(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
