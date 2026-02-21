"""Tests for FastInjectCoordinator lazy initialization.

Verifies that FastInjectCoordinator can be instantiated without
requiring fast_inject_manager to exist on main_window at construction
time (fixes startup crash when AppCoordinator is created before
Phase 2 widget initialization).
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow


@pytest.fixture
def qapp():
    """Ensure a QApplication exists for QObject-based tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeMainWindow(QMainWindow):
    """Minimal stand-in for MainWindow that can serve as QObject parent."""

    pass


class TestFastInjectCoordinatorInit:
    """Tests that FastInjectCoordinator handles deferred attribute access."""

    def test_init_without_fast_inject_manager(self, qapp):
        """Coordinator should not crash when main_window lacks fast_inject_manager."""
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )

        window = _FakeMainWindow()
        # Simulate Phase 1: fast_inject_manager does NOT exist yet
        # (no attribute set on window)

        # This must NOT raise AttributeError
        coordinator = FastInjectCoordinator(window)
        assert coordinator is not None

    def test_lazy_access_resolves_manager(self, qapp):
        """Coordinator should lazily resolve fast_inject_manager on first access."""
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )

        window = _FakeMainWindow()
        coordinator = FastInjectCoordinator(window)

        # Phase 2: manager now exists
        mock_manager = MagicMock()
        window.fast_inject_manager = mock_manager

        # Lazy access should resolve
        assert coordinator.fast_inject_manager is mock_manager

    def test_lazy_access_caches_manager(self, qapp):
        """Coordinator should cache the manager after first access."""
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )

        window = _FakeMainWindow()
        mock_manager = MagicMock()
        window.fast_inject_manager = mock_manager

        coordinator = FastInjectCoordinator(window)

        # Access twice
        mgr1 = coordinator.fast_inject_manager
        mgr2 = coordinator.fast_inject_manager
        assert mgr1 is mgr2
        assert mgr1 is mock_manager
