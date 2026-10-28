"""Compose Settings Center adapters against existing feature boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app.coordinators.settings_coordinator import SettingsCoordinator
from src.core.calendar import CalendarConfig
from src.core.theme_manager import ThemeManager
from src.gui.utils.settings_navigation import settings_navigation
from src.gui.widgets.spell_check_controller import SpellCheckController
from src.services.settings_snapshot import SettingsSnapshotWorker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow


def compose_settings(window: MainWindow) -> SettingsCoordinator:
    """Bind narrow endpoints; no new DatabaseWorker or ConnectionManager feature slots."""

    def context() -> dict[str, Any]:
        world = window.current_world
        return {
            "database": str(window.db_path),
            "name": world.name if world else "World",
            "created_at": world.manifest.created_at if world else 0,
            "assets_dir": str(world.assets_path) if world else None,
        }

    coordinator = SettingsCoordinator(
        context, window.command_coordinator.execute_command, window
    )
    database_worker = window.worker
    endpoint = SettingsSnapshotWorker(lambda: database_worker.db_service)
    endpoint.moveToThread(window.worker_thread)
    window.worker_thread.finished.connect(endpoint.deleteLater)
    coordinator.snapshot_requested.connect(
        endpoint.load, Qt.ConnectionType.QueuedConnection
    )
    endpoint.loaded.connect(coordinator.on_snapshot, Qt.ConnectionType.QueuedConnection)
    coordinator.index_rebuilt.connect(
        endpoint.mark_index_rebuilt, Qt.ConnectionType.QueuedConnection
    )
    endpoint.index_state_changed.connect(
        coordinator.refresh_world, Qt.ConnectionType.QueuedConnection
    )
    # Retain the worker-side QObject; its database provider is only called in load().
    coordinator._snapshot_worker = endpoint
    window.worker.initialized.connect(
        lambda success: coordinator.refresh_world() if success else None,
        Qt.ConnectionType.QueuedConnection,
    )
    window.worker.command_finished.connect(
        coordinator.on_command_finished, Qt.ConnectionType.QueuedConnection
    )
    window.worker_manager.save_ai_preferences_requested.connect(
        lambda _preferences: coordinator.refresh_world()
    )
    settings_navigation().requested.connect(coordinator.open_settings)
    settings_navigation().contextual_changed.connect(coordinator.set_contextual)

    def local_changed(values: dict[str, Any]) -> None:
        _refresh_local_consumers(window, values)
        _apply_effective_theme(coordinator)

    def world_changed(values: dict[str, Any]) -> None:
        window.editor_coordinator.auto_create_relations = values["world.auto_relations"]
        excluded = list(values["world.excluded_attributes"])
        window.worker_manager.index_excluded_attributes = excluded
        window.ai_search_manager.index_excluded_attributes = excluded
        _apply_effective_theme(coordinator)
        _refresh_world_consumers(window, values)

    coordinator.preferences_changed.connect(local_changed)
    coordinator.world_changed.connect(world_changed)
    coordinator.world_form_created.connect(
        window.app_coordinator.icon_library.attach_draft
    )
    coordinator.icon_picker_created.connect(
        window.app_coordinator.icon_library.attach_picker
    )
    coordinator.operation_requested.connect(
        lambda operation: _operation(window, coordinator, operation)
    )

    def rebuild_finished(_indexed: int, _unchanged: int, failed: int) -> None:
        request, coordinator.rebuild_request = coordinator.rebuild_request, None
        if request is not None and not failed and request["full"]:
            coordinator.index_rebuilt.emit(request)

    window.worker.index_rebuild_finished.connect(
        rebuild_finished, Qt.ConnectionType.QueuedConnection
    )
    coordinator.connection_requested.connect(
        lambda request: _probe(coordinator, request)
    )
    coordinator.credential_warnings = coordinator.local.migrate_credentials()
    coordinator.refresh_world()
    return coordinator


def _apply_effective_theme(coordinator: SettingsCoordinator) -> None:
    local = coordinator.local.snapshot()
    effective = coordinator.world_values.get("world.theme") or local["appearance.theme"]
    manager = ThemeManager()
    if effective != manager.current_theme_name:
        manager.set_theme(str(effective), persist=False)


def _refresh_local_consumers(window: MainWindow, values: dict[str, Any]) -> None:
    if "longform_auto_refresh" in values:
        window.longform_editor.set_refresh_button_visible(
            not values["longform_auto_refresh"]
        )
    if "timeline/snap_playhead_to_events" in values:
        control = window.timeline.chk_snap_playhead_to_events
        blocked = control.blockSignals(True)
        control.setChecked(values["timeline/snap_playhead_to_events"])
        control.blockSignals(blocked)
        window.timeline.view.set_playhead_event_snapping(control.isChecked())
    if "timeline/show_dependencies" in values:
        control = window.timeline.chk_show_dependencies
        blocked = control.blockSignals(True)
        control.setChecked(values["timeline/show_dependencies"])
        control.blockSignals(blocked)
        window.timeline.view.set_dependencies_visible(control.isChecked())
    panel = window.analysis_panel
    if panel is not None and "analysis/editorial_checks" in values:
        control = panel.editorial_checks
        blocked = control.blockSignals(True)
        control.setChecked(values["analysis/editorial_checks"])
        control.blockSignals(blocked)
    app = QApplication.instance()
    if app is not None:
        for controller in app.findChildren(SpellCheckController):
            controller.refresh_settings()
        from src.gui.widgets.wiki_text_edit import WikiTextEdit

        for widget in app.findChildren(WikiTextEdit):
            widget.action_spell_check.setChecked(
                widget.editor.spell_check._settings.enabled
            )
    if any(key.startswith("ai_") or key.startswith("secret.") for key in values):
        window.ai_search_manager._on_settings_saved()
    if any(key.startswith("backup_") for key in values):
        window.backup_coordinator.apply_backup_settings()


def _refresh_world_consumers(window: MainWindow, values: dict[str, Any]) -> None:
    # Only committed snapshots reach runtime caches and feature views.
    if values.get("world.ai"):
        window.ai_search_manager.on_ai_preferences_loaded(values["world.ai"])
    grouping = values.get("world.grouping")
    window.grouping_manager.on_grouping_config_loaded(grouping)
    if not grouping:
        window.timeline.clear_grouping()
    if values.get("world.calendar"):
        config = CalendarConfig.from_dict(values["world.calendar"])
        current = getattr(window, "calendar_converter", None)
        if current is None or current._config.to_dict() != config.to_dict():
            window.time_coordinator.on_calendar_config_loaded(config)
    window.data_coordinator.load_graph_data()


def _operation(
    window: MainWindow, coordinator: SettingsCoordinator, operation: str
) -> None:
    if operation == "index-status":
        window.ai_search_manager.refresh_search_index_status()
    else:
        if coordinator.rebuild_request is not None:
            return
        coordinator.rebuild_request = {
            "database": str(window.db_path),
            "full": operation == "all",
            "excluded_attributes": list(
                coordinator.world_values.get("world.excluded_attributes", [])
            ),
        }
        window.ai_search_manager.rebuild_search_index(operation)


def _probe(coordinator: SettingsCoordinator, request: dict[str, Any]) -> None:
    """Run model discovery off the GUI thread, without persisting draft inputs."""
    from src.gui.dialogs.ai_settings_dialog import LMStudioDiscoveryWorker

    view = coordinator.view
    if view is None or getattr(coordinator, "_probe_worker", None) is not None:
        return
    try:
        url = normalize_probe_url(request)
    except ValueError as exc:
        view.message.setText(str(exc))
        return
    worker = LMStudioDiscoveryWorker(
        url, request["key"], min(request["timeout"], 10), coordinator
    )
    coordinator._probe_worker = worker
    worker.models_discovered.connect(
        view.ai._on_models_discovered, Qt.ConnectionType.QueuedConnection
    )
    worker.discovery_failed.connect(
        view.message.setText, Qt.ConnectionType.QueuedConnection
    )

    def finished() -> None:
        coordinator._probe_worker = None
        worker.deleteLater()

    worker.finished.connect(finished)
    app = QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(worker.wait)
    worker.start()


def normalize_probe_url(request: dict[str, Any]) -> str:
    """Validate draft connection input before starting a network worker."""
    from src.services.lmstudio_config import normalize_lmstudio_base_url

    return normalize_lmstudio_base_url(str(request["url"]))
