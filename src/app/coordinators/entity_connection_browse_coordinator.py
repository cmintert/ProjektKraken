"""GUI-local page lifecycle independent of generation preparation."""

import uuid
from collections.abc import Callable
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.services.entity_connection_browse_service import PAGE_SIZE


class EntityConnectionBrowseCoordinator(QObject):
    """Coalesce requests and append only matching, single-revision pages."""

    requested = Signal(dict)
    revision_changed = Signal()

    def __init__(
        self,
        view: AuthoringContextWidget,
        query: Callable[[], dict[str, Any]],
        parent: QObject | None = None,
    ) -> None:
        """Bind a view and query provider without depending on MainWindow."""
        super().__init__(parent)
        self.view = view
        self._query_provider = query
        self._session = str(uuid.uuid4())
        self._generation = 0
        self._identity = ""
        self._query: dict[str, Any] = {}
        self._inputs: dict[str, Any] = {}
        self._cursor: dict[str, Any] | None = None
        self._rows: list[dict[str, Any]] = []
        self._busy = False
        self._checking = False
        self._page_start = 0
        self._done = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check)
        self._timer.start()
        view.connections_more_requested.connect(self.load_more)

    @Slot()
    def stop(self) -> None:
        """Stop scheduling before the owning database thread shuts down."""
        self._timer.stop()
        self.invalidate()

    @Slot()
    def invalidate(self) -> None:
        """Advance own-write generation and cancel continuation immediately."""
        self._generation += 1
        self._identity = ""
        self._busy = False
        self._checking = False
        self._cursor = None
        self._rows = []
        self._done = False
        self.view.set_connection_page(
            [],
            "Connections changed; refreshing…",
            False,
            entity_id=self._query.get("entity_id", ""),
        )

    @Slot()
    def restart(self) -> None:
        """Start the first page using the currently accepted editor inputs."""
        self._identity = str(uuid.uuid4())
        self._inputs = dict(self._query_provider())
        self._query = self._inputs | {
            "session": self._session,
            "generation": self._generation,
        }
        self._cursor = None
        self._rows = []
        self._busy = False
        self._checking = False
        self._done = False
        if not self._query.get("entity_id"):
            self.view.set_connection_page(
                [], "Select a saved Entity.", False, entity_id=""
            )
            return
        self.load_more()

    @Slot()
    def load_more(self) -> None:
        """Request a logical page; continuation never touches the AI preview."""
        if self._busy or self._done or not self._identity:
            return
        self._page_start = len(self._rows)
        self._dispatch()

    def _dispatch(self) -> None:
        self._busy = True
        self.view.set_connection_page(
            self._rows,
            "Loading saved connections…",
            False,
            entity_id=self._query["entity_id"],
            loading=True,
        )
        self.requested.emit(
            {
                "kind": "page",
                "request_id": self._identity,
                "query": self._query,
                "cursor": self._cursor,
                "remaining": PAGE_SIZE - (len(self._rows) - self._page_start),
            }
        )

    @Slot(dict)
    def accept(self, response: dict[str, Any]) -> None:
        """Ignore obsolete results before modifying rows or requesting more work."""
        if response["request_id"] != self._identity:
            return
        current = self._query_provider()
        if current != self._inputs:
            self.restart()
            return
        if response.get("stale"):
            self.invalidate()
            self.revision_changed.emit()
            return
        if response["kind"] == "check":
            self._checking = False
            return
        self._busy = False
        if response.get("error"):
            self.view.set_connection_page(
                self._rows,
                "Connections could not be loaded. Retry to continue.",
                True,
                retry=True,
                entity_id=self._query["entity_id"],
            )
            return
        self._cursor = response["cursor"]
        self._rows.extend(response["rows"])
        self._done = response["done"]
        if not self._done and len(self._rows) - self._page_start < PAGE_SIZE:
            self._dispatch()
            return
        total = response["eligible_total"]
        status = f"{len(self._rows)} loaded"
        status += (
            "; all eligible connections loaded."
            if total is not None
            else "; total not yet known."
        )
        if self._cursor["excluded"]:
            status += (
                f" {self._cursor['excluded']} checked links excluded by date so far."
            )
        if self._cursor["unreadable"]:
            status += f" {self._cursor['unreadable']} links have unavailable endpoints or timing; results are partial."
        self.view.set_connection_page(
            self._rows,
            status,
            not self._done,
            reveal=self._page_start > 0,
            entity_id=self._query["entity_id"],
        )

    @Slot()
    def _check(self) -> None:
        """Poll only a visible idle browser, with at most one check outstanding."""
        if not shiboken6.isValid(self.view):
            self._timer.stop()
            return
        if not self.view.isVisible() or self._busy or self._checking:
            return
        if not self._identity:
            self.restart()
        elif self._cursor is not None:
            self._checking = True
            self.requested.emit(
                {
                    "kind": "check",
                    "request_id": self._identity,
                    "revision": self._cursor["revision"],
                }
            )
