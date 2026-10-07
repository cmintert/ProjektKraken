"""Bind document browse gestures separately from deliberate inspector opening."""

from PySide6.QtCore import QObject

from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.gui.widgets.longform.editor import LongformEditorWidget


class LongformNavigationController(QObject):
    """Keep document gestures local and delegate guarded inspection intent."""

    def __init__(
        self, view: LongformEditorWidget, navigation: NavigationCoordinator
    ) -> None:
        """Bind completed gestures without treating local selection as navigation."""
        super().__init__(view)
        self.navigation = navigation
        view.browse_requested.connect(self.browse)
        view.open_requested.connect(self.open)
        view.link_clicked.connect(self.open_link)
        view.gesture_started.connect(self.cancel)

    def browse(self, kind: str, item_id: str) -> None:
        """Inspect only an already-visible inspector in another workspace zone."""
        self.cancel()
        self.navigation.set_global_selection(
            kind, item_id, source_panel="longform", reveal=False
        )

    def open(self, kind: str, item_id: str) -> None:
        """Reveal the inspector only through an explicit navigation action."""
        self.cancel()
        self.navigation.set_global_selection(kind, item_id, source_panel="longform")

    def cancel(self) -> None:
        """Supersede any document navigation waiting on a draft save."""
        self.navigation.cancel_source_navigation("longform")

    def open_link(self, target: str) -> None:
        """Retain document origin while resolving an explicit title or wiki link."""
        self.cancel()
        self.navigation.navigate_to_entity(target, source_panel="longform")
