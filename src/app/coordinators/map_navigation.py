"""Keep spatial selection separate from deliberate inspector navigation."""

from PySide6.QtCore import QEvent, QObject

from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.gui.widgets.map_widget import MapWidget


class MapNavigationController(QObject):
    """Delegate map inspection through source-aware navigation and draft guards."""

    def __init__(self, view: MapWidget, navigation: NavigationCoordinator) -> None:
        """Bind explicit opening and invalidate superseded map navigation."""
        super().__init__(view)
        self.navigation = navigation
        view.open_inspector_requested.connect(self.open)
        view.view.viewport().installEventFilter(self)
        view.view.graphics_scene.selectionChanged.connect(self.cancel)
        view.layer_panel.layer_selected.connect(self.cancel)
        view.map_selected.connect(self.cancel)

    def browse(self, kind: str, item_id: str) -> None:
        """Update only an already-visible inspector outside the map's zone."""
        self.cancel()
        self.navigation.set_global_selection(
            kind, item_id, source_panel="map", reveal=False
        )

    def open(self, kind: str, item_id: str) -> None:
        """Reveal the inspector through a deliberate labeled action."""
        self.cancel()
        self.navigation.set_global_selection(kind, item_id, source_panel="map")

    def cancel(self) -> None:
        """Supersede map-origin navigation without cancelling a pending save."""
        self.navigation.cancel_source_navigation("map")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Invalidate older intent as soon as a new spatial gesture begins."""
        if event.type() == QEvent.Type.MouseButtonPress:
            self.cancel()
        return super().eventFilter(watched, event)
