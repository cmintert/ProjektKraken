"""Compose optional MCP through narrow feature seams, outside shell facades."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QSettings, Qt
from PySide6.QtWidgets import QApplication, QMenu

from src.app.coordinators.mcp_coordinator import McpCoordinator
from src.core.settings import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.utils.settings_navigation import request_settings
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.mcp_access_widget import McpAccessWidget
from src.gui.widgets.standard_buttons import LabelSizedToolButton

if TYPE_CHECKING:
    from src.app.coordinators.settings_coordinator import SettingsCoordinator
    from src.app.main_window import MainWindow
    from src.gui.widgets.settings_center import SettingsCenter


class _CloseAccess(QObject):
    """Revoke on a close attempt before database shutdown can begin."""

    def __init__(self, coordinator: McpCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Never intercept or change the ordinary draft/close decisions."""
        if event.type() == QEvent.Type.Close:
            self.coordinator.stop()
        return False


def compose_mcp(window: MainWindow, settings: SettingsCoordinator) -> McpCoordinator:
    """Supply only world snapshots, DB providers and existing Qt thread ownership."""
    worker = window.worker

    def context() -> dict[str, str]:
        world = window.current_world
        return {
            "world_id": str(world.id) if world else "",
            "world_name": world.name if world else "No world loaded",
            "database": (
                str(window.db_path)
                if world and window.worker_manager.database_initialized is True
                else ""
            ),
        }

    thread = window.worker_thread
    assert thread is not None

    def local_model() -> str:
        value = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP).value(
            "ai_st_model", ""
        )
        return str(value) or "sentence-transformers/all-MiniLM-L6-v2"

    coordinator = McpCoordinator(
        context, lambda: worker.db_service, thread, window, local_model=local_model
    )
    window.data_coordinator.lore_mutation_applied.connect(coordinator.invalidate)
    close_filter = _CloseAccess(coordinator)
    window.installEventFilter(close_filter)
    worker.initialized.connect(
        lambda _success: coordinator.stop(), Qt.ConnectionType.QueuedConnection
    )
    thread.finished.connect(coordinator.stop, Qt.ConnectionType.QueuedConnection)
    window.backup_coordinator.cleanup_requested.connect(coordinator.stop)
    application = QApplication.instance()
    if application is not None:
        application.aboutToQuit.connect(coordinator.stop)

    indicator = LabelSizedToolButton(window.status_bar)
    indicator.setText("MCP sharing on")
    indicator.setAccessibleName("Local MCP sharing status and stop control")
    menu = QMenu(indicator)
    menu.addAction("Stop sharing", coordinator.stop)
    menu.addAction(
        "Local AI access settings", lambda: request_settings("integrations.mcp")
    )
    indicator.setMenu(menu)
    indicator.setPopupMode(LabelSizedToolButton.ToolButtonPopupMode.InstantPopup)
    indicator.hide()
    window.status_bar.addPermanentWidget(indicator)

    def theme() -> None:
        indicator.setStyleSheet(
            StyleHelper.get_action_role_style("quiet", "QToolButton")
        )

    connect_theme(indicator, theme)
    theme()
    coordinator.changed.connect(
        lambda state: indicator.setVisible(state["state"] in {"Starting", "Active"})
    )

    def attach(view: SettingsCenter) -> None:
        form = McpAccessWidget(view)
        view.add_page("kraken", "Integrations", form)
        form.enable_requested.connect(coordinator.enable)
        form.scopes_requested.connect(coordinator.set_scopes)
        form.prepare_requested.connect(coordinator.prepare_semantic)
        form.stop_requested.connect(coordinator.stop)
        coordinator.changed.connect(form.render_state)
        form.render_state(coordinator.snapshot())

    settings.view_created.connect(attach)
    return coordinator
