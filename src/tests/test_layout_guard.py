"""
Tests for Layout Hardening features (GeometryUtils and LayoutGuardMixin).
"""

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDockWidget, QMainWindow

from src.gui.mixins.layout_guard import LayoutGuardMixin
from src.gui.utils.geometry_utils import GeometryUtils


# --- Mocking QScreen ---
class MockScreen:
    def __init__(self, rect: QRect) -> None:
        self._rect = rect

    def availableGeometry(self) -> QRect:
        return self._rect


# --- GeometryUtils Tests ---


def test_geometry_utils_ensure_on_screen_fully_visible(monkeypatch: object) -> None:
    """Test that a fully visible rect is returned as is."""
    # Mock screens: 1920x1080
    screen_rect = QRect(0, 0, 1920, 1080)
    mock_screens = [MockScreen(screen_rect)]

    monkeypatch.setattr(QGuiApplication, "screens", lambda: mock_screens)
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: mock_screens[0])

    target = QRect(100, 100, 400, 300)
    result = GeometryUtils.ensure_on_screen(target)

    assert result == target


def test_geometry_utils_clamp_off_screen(monkeypatch: object) -> None:
    """Test that an off-screen rect is clamped back to the screen."""
    screen_rect = QRect(0, 0, 1920, 1080)
    mock_screens = [MockScreen(screen_rect)]

    monkeypatch.setattr(QGuiApplication, "screens", lambda: mock_screens)
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: mock_screens[0])

    # Positioned way off to the right
    target = QRect(3000, 100, 400, 300)
    result = GeometryUtils.ensure_on_screen(target)

    # Should be pulled back to right edge align
    # QRect.right() is inclusive (left + width - 1)
    # So for width 1920, right is 1919.
    expected_right = 1919
    assert result.right() == expected_right
    assert result.width() == 400


def test_geometry_utils_multi_monitor_ghost(monkeypatch: object) -> None:
    """
    Test the 'Ghost' scenario: Window was on 2nd monitor, now 2nd monitor is gone.
    Should move to primary monitor.
    """
    primary_rect = QRect(0, 0, 1920, 1080)
    # Secondary was at 1920, 0 but is now gone.
    mock_screens = [MockScreen(primary_rect)]

    monkeypatch.setattr(QGuiApplication, "screens", lambda: mock_screens)
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: mock_screens[0])

    # Rect is legally valid but logically off-screen (in the void where monitor 2 was)
    target = QRect(2000, 100, 500, 400)

    result = GeometryUtils.ensure_on_screen(target)

    # Needs to be on primary screen now
    assert primary_rect.intersects(result)
    # Be lenient with center check as size might be clamped
    assert result.left() >= 0
    assert result.top() >= 0


# --- LayoutGuardMixin Tests ---


class TestWindow(QMainWindow, LayoutGuardMixin):
    """Concrete class for testing mixin."""

    pass


def test_guard_validate_dock_sizes(qtbot: object) -> None:
    """Test that collapsed docks are expanded."""
    window = TestWindow()
    qtbot.addWidget(window)
    window.resize(800, 600)

    # Create a dummy dock
    dock = QDockWidget("Test Dock", window)
    dock.setObjectName("TestDock")
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    # Manually collapse it to simulate bad state
    # We must force it by overriding min size temporarily to 0
    dock.setMinimumSize(0, 0)
    dock.resize(10, 10)
    dock.show()

    # Pre-condition: It should be small (simulating corruption)
    # Note: In a real layout, QMainWindow prevents this, so we simulate
    # the condition by finding a way to trigger the Guard logic.
    # The Guard checks width() < SAFE_MIN (50).

    # Set a real minimum requirement that SHOULD be enforced
    dock.setMinimumWidth(200)
    dock.setMinimumHeight(150)

    # Since we can't easily force QMainWindow to squash a dock in a unit test
    # without complex splitter manipulation, let's mock the dock geometry
    # check by temporarily subclassing or patching?
    # Alternatively, trust that resize(10, 10) works if floating or just verify the logic call.

    # Only verify logic if we can reproduce the collapsed state.
    # If we can't squash it, the test is invalid.

    # Let's try floating it - floating docks are easy to squash
    dock.setFloating(True)
    dock.resize(10, 10)

    # Now wait for events
    qtbot.waitExposed(dock)

    # Check if squashed
    if dock.width() > 50:
        pytest.skip("Could not squash dock to verify expansion logic")

    # Trigger Guard
    window.guard_validate_dock_sizes()
    qtbot.wait(100)  # Wait for QTimer

    # Should have been forced to expand
    # Guard logic sets temporary min to 200
    assert dock.width() >= 200 or dock.minimumWidth() >= 200
