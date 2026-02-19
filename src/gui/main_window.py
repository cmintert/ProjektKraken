"""VS Code-style MainWindow with dockable panes and layout persistence.

Provides an Activity Bar, dockable Explorer/Timeline/Relations/Console panes,
and a central tabbed editor area.  Layout geometry and dock state are persisted
via ``QSettings`` across application runs.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

logger = logging.getLogger(__name__)

_SETTINGS_KEY_GEOMETRY = "vscode_layout/geometry"
_SETTINGS_KEY_STATE = "vscode_layout/windowState"


class MainWindow(QMainWindow):
    """VS Code-style main window with activity bar, docks, and tabbed editors.

    Provides:
        - A left-side Activity Bar with toggle buttons for docks.
        - Explorer, Timeline, and Relations dock widgets.
        - A central ``QTabWidget`` (closable tabs) inside a ``QSplitter``.
        - A bottom Console dock (read-only ``QTextEdit`` placeholder).
        - Geometry and dock state persistence via ``QSettings``.

    Signals:
        explorer_requested: Emitted when the Explorer activity button is
            clicked.
        timeline_requested: Emitted when the Timeline activity button is
            clicked.
        relations_requested: Emitted when the Relations activity button is
            clicked.
    """

    explorer_requested = Signal()
    timeline_requested = Signal()
    relations_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the VS Code-style MainWindow.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("ProjektKraken")
        self.setMinimumSize(800, 600)
        logger.info("Initializing VS Code-style MainWindow")

        self._init_activity_bar()
        self._init_docks()
        self._init_central_area()
        self._restore_window_state()

        logger.info("MainWindow initialization complete")

    # -- Activity Bar --------------------------------------------------------

    def _init_activity_bar(self) -> None:
        """Create the left-side Activity Bar with toggle buttons."""
        self.activity_bar = QToolBar("Activity Bar", self)
        self.activity_bar.setObjectName("ActivityBar")
        self.activity_bar.setMovable(False)
        self.activity_bar.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.activity_bar)

        self._explorer_action = self.activity_bar.addAction("Explorer")
        self._explorer_action.triggered.connect(self._on_explorer_clicked)

        self._timeline_action = self.activity_bar.addAction("Timeline")
        self._timeline_action.triggered.connect(self._on_timeline_clicked)

        self._relations_action = self.activity_bar.addAction("Relations")
        self._relations_action.triggered.connect(self._on_relations_clicked)

        self._console_action = self.activity_bar.addAction("Console")
        self._console_action.triggered.connect(self._on_console_clicked)

        logger.debug("Activity bar created with 4 toggle actions")

    # -- Dock Widgets --------------------------------------------------------

    def _init_docks(self) -> None:
        """Create Explorer, Timeline, Relations, and Console dock widgets."""
        # Explorer (left)
        self.explorer_dock = QDockWidget("Explorer", self)
        self.explorer_dock.setObjectName("ExplorerDock")
        self._explorer_widget = QListWidget()
        self._explorer_widget.addItems(
            ["(placeholder) Item 1", "(placeholder) Item 2"]
        )
        self.explorer_dock.setWidget(self._explorer_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock
        )

        # Timeline (left, tabified with Explorer)
        self.timeline_dock = QDockWidget("Timeline", self)
        self.timeline_dock.setObjectName("TimelineDock")
        self._timeline_widget = QListWidget()
        self._timeline_widget.addItems(
            ["(placeholder) Event A", "(placeholder) Event B"]
        )
        self.timeline_dock.setWidget(self._timeline_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.timeline_dock
        )
        self.tabifyDockWidget(self.explorer_dock, self.timeline_dock)

        # Relations (right)
        self.relations_dock = QDockWidget("Relations", self)
        self.relations_dock.setObjectName("RelationsDock")
        self._relations_widget = QListWidget()
        self._relations_widget.addItems(
            ["(placeholder) Rel 1", "(placeholder) Rel 2"]
        )
        self.relations_dock.setWidget(self._relations_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.relations_dock
        )

        # Console (bottom)
        self.console_dock = QDockWidget("Console", self)
        self.console_dock.setObjectName("ConsoleDock")
        self._console_widget = QTextEdit()
        self._console_widget.setReadOnly(True)
        self._console_widget.setPlaceholderText("Console output...")
        self.console_dock.setWidget(self._console_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock
        )

        logger.debug(
            "Dock widgets created: Explorer, Timeline, Relations, Console"
        )

    # -- Central Editor Area -------------------------------------------------

    def _init_central_area(self) -> None:
        """Create the central tabbed editor area inside a horizontal splitter.

        The ``QTabWidget`` supports closable tabs and is wrapped in a
        ``QSplitter`` so that future secondary editor groups can be added.
        """
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(
            self._on_tab_close_requested
        )
        self._splitter.addWidget(self.editor_tabs)
        self.setCentralWidget(self._splitter)
        logger.debug("Central editor area created")

    # -- Public Toggle Methods -----------------------------------------------

    def toggle_explorer(self) -> None:
        """Toggle visibility of the Explorer dock."""
        visible = not self.explorer_dock.isVisible()
        self.explorer_dock.setVisible(visible)
        logger.debug("Explorer dock toggled: visible=%s", visible)

    def toggle_timeline(self) -> None:
        """Toggle visibility of the Timeline dock."""
        visible = not self.timeline_dock.isVisible()
        self.timeline_dock.setVisible(visible)
        logger.debug("Timeline dock toggled: visible=%s", visible)

    def toggle_relations(self) -> None:
        """Toggle visibility of the Relations dock."""
        visible = not self.relations_dock.isVisible()
        self.relations_dock.setVisible(visible)
        logger.debug("Relations dock toggled: visible=%s", visible)

    def toggle_console(self) -> None:
        """Toggle visibility of the Console dock."""
        visible = not self.console_dock.isVisible()
        self.console_dock.setVisible(visible)
        logger.debug("Console dock toggled: visible=%s", visible)

    # -- Public API ----------------------------------------------------------

    def create_new_editor_tab(self, title: str = "Untitled") -> int:
        """Add a placeholder editor tab and return its index.

        Args:
            title: The tab title.  Defaults to ``"Untitled"``.

        Returns:
            The index of the newly created tab.
        """
        editor = QTextEdit()
        editor.setPlaceholderText("Start editing...")
        index = self.editor_tabs.addTab(editor, title)
        self.editor_tabs.setCurrentIndex(index)
        logger.info(
            "New editor tab created: '%s' (index=%d)", title, index
        )
        return index

    # -- Slots (private) -----------------------------------------------------

    def _on_explorer_clicked(self, checked: bool = False) -> None:
        """Handle Explorer activity button click."""
        self.toggle_explorer()
        self.explorer_requested.emit()

    def _on_timeline_clicked(self, checked: bool = False) -> None:
        """Handle Timeline activity button click."""
        self.toggle_timeline()
        self.timeline_requested.emit()

    def _on_relations_clicked(self, checked: bool = False) -> None:
        """Handle Relations activity button click."""
        self.toggle_relations()
        self.relations_requested.emit()

    def _on_console_clicked(self, checked: bool = False) -> None:
        """Handle Console activity button click."""
        self.toggle_console()

    def _on_tab_close_requested(self, index: int) -> None:
        """Close the editor tab at *index*.

        Args:
            index: Tab index to close.
        """
        widget = self.editor_tabs.widget(index)
        self.editor_tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        logger.debug("Editor tab closed: index=%d", index)

    # -- State Persistence ---------------------------------------------------

    def _save_window_state(self) -> None:
        """Persist geometry and dock state to ``QSettings``."""
        from PySide6.QtCore import QSettings

        settings = QSettings()
        settings.setValue(_SETTINGS_KEY_GEOMETRY, self.saveGeometry())
        settings.setValue(_SETTINGS_KEY_STATE, self.saveState())
        logger.info("Window state saved")

    def _restore_window_state(self) -> None:
        """Restore geometry and dock state from ``QSettings``."""
        from PySide6.QtCore import QSettings

        settings = QSettings()
        geometry = settings.value(_SETTINGS_KEY_GEOMETRY)
        state = settings.value(_SETTINGS_KEY_STATE)
        if geometry is not None:
            self.restoreGeometry(geometry)
            logger.info("Window geometry restored")
        if state is not None:
            self.restoreState(state)
            logger.info("Window state restored")

    # -- Qt Overrides --------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Save layout before closing.

        Args:
            event: The close event.
        """
        self._save_window_state()
        super().closeEvent(event)
