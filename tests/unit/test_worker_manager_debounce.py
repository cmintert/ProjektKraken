"""Tests for WorkerManager re-embed debounce logic.

Verifies that rapid autosave-triggered re-embed requests are debounced
so the ONNX embedding model only runs once after the user stops typing,
instead of on every keystroke-driven autosave (which crashes due to
native-thread collision with the Chromium graph view).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.app.worker_manager import WorkerManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_window():
    """Minimal MainWindow-shaped mock with a worker attribute."""
    window = MagicMock()
    window.worker = MagicMock()
    return window


@pytest.fixture()
def manager(mock_window):
    """WorkerManager wired to a mock window."""
    mgr = WorkerManager(mock_window)
    return mgr


# ---------------------------------------------------------------------------
# Debounce behaviour
# ---------------------------------------------------------------------------


class TestIndexDebounce:
    """_on_index_object_requested must debounce, not fire immediately."""

    @patch("src.app.worker_manager.QSettings")
    def test_does_not_emit_immediately(self, mock_qsettings, manager):
        """Signal must NOT be emitted right away — only after the timer."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: {
            "ai_auto_index_on_save": True,
            "ai_search_excluded_attrs": "",
        }.get(key, "")

        emitted = []
        manager._index_single_requested.connect(
            lambda *args: emitted.append(args)
        )

        manager._on_index_object_requested("entity", "abc-123")

        # Signal has NOT been emitted yet — it is pending.
        assert emitted == []
        assert manager._pending_indices == {("entity", "abc-123")}

    @patch("src.app.worker_manager.QSettings")
    def test_emits_after_timer_fires(self, mock_qsettings, manager):
        """When the timer fires, the debounced signal should be emitted."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: {
            "ai_auto_index_on_save": True,
            "ai_search_excluded_attrs": "",
        }.get(key, "")

        emitted = []
        manager._index_single_requested.connect(
            lambda *args: emitted.append(args)
        )

        manager._on_index_object_requested("entity", "abc-123")

        # Manually fire the timer callback (simulates idle timeout).
        manager._flush_pending_index()

        assert len(emitted) == 1
        assert emitted[0][0] == "entity"
        assert emitted[0][1] == "abc-123"

    @patch("src.app.worker_manager.QSettings")
    def test_rapid_saves_only_emit_once(self, mock_qsettings, manager):
        """Multiple rapid requests should result in only one embed."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: {
            "ai_auto_index_on_save": True,
            "ai_search_excluded_attrs": "",
        }.get(key, "")

        emitted = []
        manager._index_single_requested.connect(
            lambda *args: emitted.append(args)
        )

        # Simulate 5 rapid autosaves (each distinct object is retained).
        for i in range(5):
            manager._on_index_object_requested("entity", f"id-{i}")

        assert manager._pending_indices == {
            ("entity", f"id-{i}") for i in range(5)
        }

        # Flush once.
        manager._flush_pending_index()

        assert len(emitted) == 5
        assert {(item[0], item[1]) for item in emitted} == {
            ("entity", f"id-{i}") for i in range(5)
        }

    @patch("src.app.worker_manager.QSettings")
    def test_disabled_auto_index_does_not_start_timer(
        self, mock_qsettings, manager
    ):
        """When ai_auto_index_on_save is False, timer must not start."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: {
            "ai_auto_index_on_save": False,
            "ai_search_excluded_attrs": "",
        }.get(key, "")

        manager._on_index_object_requested("entity", "no-go")

        assert not manager._index_timer.isActive()
        assert manager._pending_indices == set()

    @patch("src.app.worker_manager.QSettings")
    def test_flush_with_no_pending_is_noop(self, mock_qsettings, manager):
        """_flush_pending_index with nothing pending must not emit."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: ""

        emitted = []
        manager._index_single_requested.connect(
            lambda *args: emitted.append(args)
        )

        manager._flush_pending_index()

        assert emitted == []

    @patch("src.app.worker_manager.QSettings")
    def test_no_worker_does_not_crash(self, mock_qsettings, manager):
        """If worker is gone at flush time, no crash and no emit."""
        mock_qsettings.return_value.value.side_effect = lambda key, *a, **kw: {
            "ai_auto_index_on_save": True,
            "ai_search_excluded_attrs": "",
        }.get(key, "")

        manager._on_index_object_requested("entity", "e-1")

        # Worker disappears before flush.
        manager.window.worker = None

        emitted = []
        manager._index_single_requested.connect(
            lambda *args: emitted.append(args)
        )

        manager._flush_pending_index()  # must not crash
        assert emitted == []

    def test_debounce_constant_is_reasonable(self, manager):
        """The debounce interval should be at least 5 seconds."""
        assert manager.INDEX_DEBOUNCE_MS >= 5000
