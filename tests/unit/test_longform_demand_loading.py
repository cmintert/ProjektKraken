"""Tests for demand-driven Longform hydration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.app.longform_manager import LongformManager


def _window(active_panel: str = "entity") -> MagicMock:
    window = MagicMock()
    window.workspace.panel_ids.return_value = ["entity", "longform"]
    window.workspace.panel_zone.return_value = "center"
    window.workspace.zone_visible.return_value = True
    window.workspace.active_panel.return_value = active_panel
    window.longform_filter_config = {}
    return window


def test_hidden_longform_invalidation_does_not_query(qapp) -> None:
    window = _window()
    manager = LongformManager(window)

    with patch("src.app.longform_manager.invoke_queued") as invoke:
        manager.mark_dirty()
        qapp.processEvents()

    invoke.assert_not_called()


def test_repeated_active_longform_invalidations_coalesce(qtbot) -> None:
    window = _window("longform")
    manager = LongformManager(window)

    with patch("src.app.longform_manager.invoke_queued") as invoke:
        manager.mark_dirty()
        manager.mark_dirty()
        qtbot.wait(120)

    invoke.assert_called_once()


def test_hidden_longform_result_renders_from_cache_on_activation(qapp) -> None:
    window = _window("longform")
    manager = LongformManager(window)
    with patch("src.app.longform_manager.invoke_queued"):
        manager.load_longform_sequence()
    window.workspace.active_panel.return_value = "entity"

    sequence = [{"id": "event-1"}]
    manager.on_longform_sequence_loaded(sequence)

    window.longform_editor.load_sequence.assert_not_called()
    assert window.data_coordinator.cached_longform_sequence == sequence

    window.workspace.active_panel.return_value = "longform"
    manager.on_panel_activated("longform")
    window.longform_editor.load_sequence.assert_called_once_with(sequence)
