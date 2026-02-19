"""MainWindow with dockable panes and layout persistence.

Provides an Activity Bar, dockable Explorer/Timeline/Relations/Console panes,
and a central tabbed editor area.  Layout geometry and dock state are persisted
via ``QSettings`` across application runs.

Real production widgets from the ``src.gui.widgets`` package are used for the
Explorer (``UnifiedListWidget``), Timeline (``TimelineWidget``), and Relations
(``GraphWidget``) docks.  Event and Entity editors are available as central
editor tabs.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

logger = logging.getLogger(__name__)

_SETTINGS_KEY_GEOMETRY = "vscode_layout/geometry"
_SETTINGS_KEY_STATE = "vscode_layout/windowState"

_DOCK_FEATURES = (
    QDockWidget.DockWidgetFeature.DockWidgetMovable
    | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    | QDockWidget.DockWidgetFeature.DockWidgetClosable
)


class MainWindow(QMainWindow):
    """Main window with activity bar, docks, and tabbed editors.

    Provides:
        - A left-side Activity Bar with toggle buttons for docks.
        - Explorer (``UnifiedListWidget``), Timeline (``TimelineWidget``),
          and Relations (``GraphWidget``) dock widgets.
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
        item_selected: Forwarded from the Explorer when an item is selected.
            Carries ``(item_type, item_id)`` strings.
        event_selected: Forwarded from the Timeline when an event is clicked.
            Carries the event ID string.
        node_clicked: Forwarded from the Relations graph when a node is
            clicked.  Carries ``(object_type, object_id)`` strings.
    """

    explorer_requested = Signal()
    timeline_requested = Signal()
    relations_requested = Signal()
    item_selected = Signal(str, str)
    event_selected = Signal(str)
    node_clicked = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the MainWindow.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("ProjektKraken")
        self.setMinimumSize(800, 600)
        logger.info("Initializing MainWindow")

        self._configure_dock_options()
        self._init_activity_bar()
        self._init_docks()
        self._init_central_area()
        self._restore_window_state()

        logger.info("MainWindow initialization complete")

    # -- Dock options --------------------------------------------------------

    def _configure_dock_options(self) -> None:
        """Enable animated docks, nesting, and tabbed docking."""
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QTabWidget.TabPosition.North,
        )
        # Map corners so left/right docks span full height.
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(
            Qt.Corner.BottomRightCorner,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        logger.debug("Dock options configured: nested, tabbed, animated")

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
        """Create Explorer, Timeline, Relations, and Console dock widgets.

        Uses production widgets from ``src.gui.widgets``:
        - Explorer → ``UnifiedListWidget``
        - Timeline → ``TimelineWidget``
        - Relations → ``GraphWidget``
        - Console  → read-only ``QTextEdit`` (placeholder)

        All docks are movable, floatable, closable, and allowed in every
        dock area so the user can freely rearrange the layout.
        """
        # Explorer (left) – UnifiedListWidget
        self.explorer_dock = QDockWidget("Explorer", self)
        self.explorer_dock.setObjectName("ExplorerDock")
        self.explorer_dock.setFeatures(_DOCK_FEATURES)
        self.explorer_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.unified_list = UnifiedListWidget()
        self.unified_list.item_selected.connect(self.item_selected)
        self.explorer_dock.setWidget(self.unified_list)
        self._apply_dock_size_policy(self.explorer_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)

        # Timeline (left, tabified with Explorer) – TimelineWidget
        self.timeline_dock = QDockWidget("Timeline", self)
        self.timeline_dock.setObjectName("TimelineDock")
        self.timeline_dock.setFeatures(_DOCK_FEATURES)
        self.timeline_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.timeline = TimelineWidget()
        self.timeline.event_selected.connect(self.event_selected)
        self.timeline_dock.setWidget(self.timeline)
        self._apply_dock_size_policy(self.timeline_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.timeline_dock)
        self.tabifyDockWidget(self.explorer_dock, self.timeline_dock)

        # Relations (right) – GraphWidget
        self.relations_dock = QDockWidget("Relations", self)
        self.relations_dock.setObjectName("RelationsDock")
        self.relations_dock.setFeatures(_DOCK_FEATURES)
        self.relations_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.graph_widget = GraphWidget()
        self.graph_widget.node_clicked.connect(self.node_clicked)
        self.relations_dock.setWidget(self.graph_widget)
        self._apply_dock_size_policy(self.relations_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.relations_dock)

        # Console (bottom)
        self.console_dock = QDockWidget("Console", self)
        self.console_dock.setObjectName("ConsoleDock")
        self.console_dock.setFeatures(_DOCK_FEATURES)
        self.console_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._console_widget = QTextEdit()
        self._console_widget.setReadOnly(True)
        self._console_widget.setPlaceholderText("Console output...")
        self.console_dock.setWidget(self._console_widget)
        self._apply_dock_size_policy(self.console_dock, min_h=100)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)

        logger.debug(
            "Dock widgets created: Explorer (UnifiedListWidget), "
            "Timeline (TimelineWidget), Relations (GraphWidget), Console"
        )

    @staticmethod
    def _apply_dock_size_policy(
        dock: QDockWidget,
        min_w: int = 250,
        min_h: int = 150,
    ) -> None:
        """Set minimum size and a Preferred/stretch-1 size policy on *dock*.

        Args:
            dock: The dock widget to configure.
            min_w: Minimum width in pixels.
            min_h: Minimum height in pixels.
        """
        dock.setMinimumWidth(min_w)
        dock.setMinimumHeight(min_h)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHorizontalStretch(1)
        policy.setVerticalStretch(1)
        dock.setSizePolicy(policy)

    # -- Central Editor Area -------------------------------------------------

    def _init_central_area(self) -> None:
        """Create the central tabbed editor area inside a horizontal splitter.

        The ``QTabWidget`` supports closable tabs and is wrapped in a
        ``QSplitter`` so that future secondary editor groups can be added.
        An ``EventEditorWidget`` and an ``EntityEditorWidget`` are added as
        default tabs.
        """
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(4)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._on_tab_close_requested)

        # Default editor tabs
        self.event_editor = EventEditorWidget()
        self.entity_editor = EntityEditorWidget()
        self.editor_tabs.addTab(self.event_editor, "Event Editor")
        self.editor_tabs.addTab(self.entity_editor, "Entity Editor")

        self._splitter.addWidget(self.editor_tabs)
        self._splitter.setStretchFactor(0, 1)
        self.setCentralWidget(self._splitter)
        logger.debug("Central editor area created with Event and Entity editor tabs")

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
        logger.info("New editor tab created: '%s' (index=%d)", title, index)
        return index

    # -- Slots (private) -----------------------------------------------------

    def _on_explorer_clicked(self, checked: bool = False) -> None:
        """Handle Explorer activity button click.

        Args:
            checked: Action toggle state from ``QAction.triggered``.
                Unused; visibility is derived from the dock's current state.
        """
        self.toggle_explorer()
        self.explorer_requested.emit()

    def _on_timeline_clicked(self, checked: bool = False) -> None:
        """Handle Timeline activity button click.

        Args:
            checked: Action toggle state from ``QAction.triggered``.
                Unused; visibility is derived from the dock's current state.
        """
        self.toggle_timeline()
        self.timeline_requested.emit()

    def _on_relations_clicked(self, checked: bool = False) -> None:
        """Handle Relations activity button click.

        Args:
            checked: Action toggle state from ``QAction.triggered``.
                Unused; visibility is derived from the dock's current state.
        """
        self.toggle_relations()
        self.relations_requested.emit()

    def _on_console_clicked(self, checked: bool = False) -> None:
        """Handle Console activity button click.

        Args:
            checked: Action toggle state from ``QAction.triggered``.
                Unused; visibility is derived from the dock's current state.
        """
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
