"""Outer-window geometry recovery tests."""

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication

from src.gui.utils.geometry_utils import GeometryUtils


class _Screen:
    def __init__(self, rectangle: QRect) -> None:
        self._rectangle = rectangle

    def availableGeometry(self) -> QRect:  # noqa: N802
        return self._rectangle


def test_geometry_fully_on_screen_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screen = _Screen(QRect(0, 0, 1920, 1080))
    monkeypatch.setattr(QGuiApplication, "screens", lambda: [screen])
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: screen)
    target = QRect(100, 100, 400, 300)

    assert GeometryUtils.ensure_on_screen(target) == target


def test_geometry_from_removed_monitor_moves_to_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = QRect(0, 0, 1920, 1080)
    screen = _Screen(primary)
    monkeypatch.setattr(QGuiApplication, "screens", lambda: [screen])
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: screen)

    result = GeometryUtils.ensure_on_screen(QRect(3000, 100, 400, 300))

    assert primary.intersects(result)
    assert result.right() == primary.right()
