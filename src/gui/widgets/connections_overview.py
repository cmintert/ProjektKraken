"""Shared, identity-based Connections browser for Entity and Event inspectors."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QFontMetrics,
    QKeyEvent,
    QResizeEvent,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.connection_presentation import (
    ENTITY_GROUPS,
    EVENT_GROUPS,
    ConnectionRow,
    project_connections,
)
from src.gui.widgets.menu_caret import PhosphorToolMenuButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.standard_buttons import DestructiveButton, StandardButton

ROW_ROLE = int(Qt.ItemDataRole.UserRole)


class ConnectionDelegate(QStyledItemDelegate):
    """Keep connection rows on one line with consistent vertical breathing room."""

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Measure one text line; the view elides overflow with a full tooltip."""
        view = self.parent()
        assert isinstance(view, QTreeView)
        width = max(40, view.viewport().width() - view.indentation() * 2 - 16)
        metrics = QFontMetrics(view.font())
        return QSize(width, metrics.height() + 16)


class ConnectionsOverview(QWidget):
    """Render relation snapshots and emit intent without owning business services."""

    edit_requested = Signal(dict)
    remove_requested = Signal(dict)
    navigate_requested = Signal(str)
    connect_requested = Signal(str)
    selection_changed = Signal(str)

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        """Create one browser, with a guard supplied by its draft owner."""
        super().__init__(parent)
        self.kind = kind
        self.selected_id = ""
        self.object_id = ""
        self.object_name = ""
        self.rows: list[ConnectionRow] = []
        self.before_selection: Callable[[], bool] = lambda: True
        self._rendering = False
        self._expanded: dict[str, bool] = {}
        self._directions = {"incoming", "outgoing"}
        self._groups = set(EVENT_GROUPS if kind == "event" else ENTITY_GROUPS)
        self._include_references = True
        self._editable = True
        self._secondary_actions: list[Any] = []
        self._snapshots: tuple[list[dict[str, Any]], list[dict[str, Any]]] = ([], [])
        self._time: float | None = None
        self._calendar: CalendarConverter | None = None
        layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(layout)
        self.heading = QLabel("Connections")
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.connect_button = declare_inspection(
            StandardButton("Connect…"),
            "connections-connect|relations.create|help-connections-connect",
        )
        self.connect_button.clicked.connect(self._connect)
        self.search = declare_inspection(
            QLineEdit(), "connections-search|relations.create|help-connections-search"
        )
        self.search.setPlaceholderText("Find a connection…")
        self.search.setAccessibleName("Find a connection")
        self.search.textChanged.connect(self._render)
        self.filters = declare_inspection(
            PhosphorToolMenuButton(),
            "connections-filters|relations.create|help-connections-filters",
        )
        self.filters.setText("Filters")
        self.filters.setMenu(self._filter_menu())
        self.filters.setPopupMode(
            PhosphorToolMenuButton.ToolButtonPopupMode.InstantPopup
        )
        header = OverflowToolBar()
        self.header_actions = header
        header.add_button(self.connect_button, priority=10, pinned=True)
        layout.addWidget(header)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.filters)
        layout.addLayout(search_row)
        self.tree = declare_inspection(
            QTreeView(),
            "connections-overview|relations.create|help-connections-overview",
        )
        self.tree.setAccessibleName("Connections by meaning")
        self.tree.setHeaderHidden(True)
        self.tree.setWordWrap(False)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformRowHeights(False)
        self.tree.setMinimumHeight(80)
        self.model = QStandardItemModel(self)
        self.tree.setModel(self.model)
        self.tree.setItemDelegate(ConnectionDelegate(self.tree))
        self.tree.selectionModel().currentChanged.connect(self._selection)
        self.tree.doubleClicked.connect(self._activate)
        self.tree.expanded.connect(lambda index: self._expansion(index, True))
        self.tree.collapsed.connect(lambda index: self._expansion(index, False))
        self.tree.installEventFilter(self)
        self.tree.viewport().installEventFilter(self)
        self._origin_focus: QWidget | None = None
        layout.addWidget(self.tree, 1)
        self.summary = QLabel("No relationship selected")
        self.summary.setWordWrap(True)
        self.summary.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        selection_row = QHBoxLayout()
        selection_row.addWidget(self.summary, 1)
        self.edit_button = declare_inspection(
            StandardButton("Edit"),
            "connections-edit|relations.create|help-connections-edit",
        )
        self.edit_button.clicked.connect(self.edit_selected)
        selection_row.addWidget(self.edit_button)
        layout.addLayout(selection_row)
        self.go_button = declare_inspection(
            StandardButton("Go to connected entry", self),
            "connections-navigate|relations.create|help-connections-navigate",
        )
        self.go_button.clicked.connect(self.navigate_selected)
        self.remove_button = declare_inspection(
            DestructiveButton("Remove", self),
            "connections-remove|relations.create|help-connections-remove",
        )
        self.remove_button.clicked.connect(self.remove_selected)
        self.go_button.hide()
        self.remove_button.hide()
        self._update_summary()
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def add_secondary_actions(self, menu: QMenu) -> None:
        """Keep navigation/removal discoverable without crowding the selection row."""
        menu.addSeparator()
        for button in (self.go_button, self.remove_button):
            action = menu.addAction(button.text())
            action.setProperty("krakenHelpEquivalent", button)
            action.setEnabled(button.isEnabled())
            action.triggered.connect(button.click)
            self._secondary_actions.append((action, button))

    def _filter_menu(self) -> QMenu:
        menu = QMenu(self)
        for label, value in (("Incoming", "incoming"), ("Outgoing", "outgoing")):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(
                lambda checked, key=value: self._filter_set(
                    self._directions, key, checked
                )
            )
        menu.addSeparator()
        for group in EVENT_GROUPS if self.kind == "event" else ENTITY_GROUPS:
            if group == "References":
                continue
            action = menu.addAction(group.replace("&", "&&"))
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(
                lambda checked, key=group: self._filter_set(self._groups, key, checked)
            )
        action = menu.addAction("Include References")
        action.setCheckable(True)
        action.setChecked(True)
        action.toggled.connect(self._references)
        return menu

    def _filter_set(self, values: set[str], key: str, checked: bool) -> None:
        if checked:
            values.add(key)
        else:
            values.discard(key)
        self._render()

    def _references(self, checked: bool) -> None:
        self._include_references = checked
        self._render()

    def _apply_theme(self, *_args: Any) -> None:
        self.tree.setStyleSheet(StyleHelper.get_connections_overview_style())
        self.filters.setStyleSheet(
            StyleHelper.get_tool_button_style() + StyleHelper.get_menu_caret_style()
        )
        self._fit_height()

    def _connect(self) -> None:
        if self._editable:
            self.connect_requested.emit("related")

    def set_editable(self, editable: bool) -> None:
        """Keep browsing available while historical snapshots prohibit mutation."""
        self._editable = editable
        self.connect_button.setEnabled(editable)
        self._update_summary()

    def set_relations(
        self,
        outgoing: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
        object_id: str,
        name: str,
    ) -> None:
        """Refresh read-only rows without rebuilding the independent draft."""
        if object_id != self.object_id:
            self.selected_id = ""
            self._expanded.clear()
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        self.object_id, self.object_name = object_id, name
        self._snapshots = outgoing, incoming
        self._project()

    def set_time_context(
        self,
        time: float,
        calendar: CalendarConverter | None,
    ) -> None:
        """Re-evaluate status; changing viewing time never filters assertions."""
        self._time, self._calendar = time, calendar
        self._project()

    def _project(self) -> None:
        self.rows = project_connections(
            *self._snapshots,
            self.kind,
            self.object_id,
            self.object_name,
            self._time,
            self._calendar,
        )
        self._render()

    def selected_row(self) -> ConnectionRow | None:
        """Return the selected assertion even when a filter hides it."""
        return next(
            (r for r in self.rows if r.snapshot.get("id") == self.selected_id), None
        )

    def _visible(self, row: ConnectionRow) -> bool:
        query = self.search.text().casefold().strip()
        return (
            row.direction in self._directions
            and row.group in self._groups
            and (self._include_references or row.group != "References")
            and query
            in f"{row.title} {row.assertion} {row.snapshot['rel_type']}".casefold()
        )

    def _render(self, *_args: Any) -> None:
        anchor = self.tree.indexAt(QPoint(1, 1)).data(ROW_ROLE)
        scroll = self.tree.verticalScrollBar().value()
        self._rendering = True
        self.model.clear()
        groups = EVENT_GROUPS if self.kind == "event" else ENTITY_GROUPS
        self._indices: dict[str, QModelIndex] = {}
        visible = [row for row in self.rows if self._visible(row)]
        for group in groups:
            children = [row for row in visible if row.group == group]
            if not children:
                continue
            item = QStandardItem(f"{group} ({len(children)})")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(group, ROW_ROLE + 1)
            for row in children:
                child = QStandardItem(row.text)
                child.setData(row.snapshot["id"], ROW_ROLE)
                child.setToolTip(f"{row.assertion}\n{row.timing}")
                child.setEditable(False)
                item.appendRow(child)
            self.model.appendRow(item)
            self.tree.setExpanded(
                item.index(), self._expanded.get(group, group != "References")
            )
            for index, row in enumerate(children):
                self._indices[row.snapshot["id"]] = item.child(index).index()
        self._restore_selection()
        if anchor in self._indices:
            self.tree.scrollTo(
                self._indices[anchor], QAbstractItemView.ScrollHint.PositionAtTop
            )
        else:
            self.tree.verticalScrollBar().setValue(scroll)
        self._restore_expansion()
        self._rendering = False
        self.heading.setText(f"Connections — {self.object_name} ({len(self.rows)})")
        self._update_summary()

    def _restore_expansion(self) -> None:
        # Qt may expand ancestors while restoring current/scroll targets.
        for index in range(self.model.rowCount()):
            group_index = self.model.index(index, 0)
            group_name = str(group_index.data(ROW_ROLE + 1))
            self.tree.setExpanded(
                group_index, self._expanded.get(group_name, group_name != "References")
            )

    def _restore_selection(self) -> None:
        self.tree.selectionModel().setCurrentIndex(
            self._indices.get(self.selected_id, QModelIndex()),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self._restore_expansion()

    def _expansion(self, index: QModelIndex, expanded: bool) -> None:
        if not self._rendering:
            self._expanded[str(index.data(ROW_ROLE + 1))] = expanded
            self._update_summary()

    def select_relation(self, relation_id: str, *, guarded: bool = True) -> bool:
        """Select by identity, resolving an independent draft before user navigation."""
        focus = self._origin_focus or QApplication.focusWidget()
        self._origin_focus = None
        if relation_id == self.selected_id:
            return True
        if guarded and not self.before_selection():
            if focus is not None:
                focus.setFocus()
            return False
        self.selected_id = relation_id
        self._rendering = True
        self._restore_selection()
        self._rendering = False
        self._update_summary()
        self.selection_changed.emit(relation_id)
        return True

    def _selection(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self._rendering:
            return
        if current.data(ROW_ROLE + 1):
            return
        relation_id = str(current.data(ROW_ROLE) or "")
        if not self.select_relation(relation_id):
            self._rendering = True
            self._restore_selection()
            self._rendering = False

    def _update_summary(self) -> None:
        row = self.selected_row()
        hidden = self.selected_id not in getattr(self, "_indices", {})
        if not hidden:
            hidden = not self.tree.isExpanded(self._indices[self.selected_id].parent())
        self.summary.setText(
            f"Selected: {row.title}"
            + (" (hidden by filters or collapsed group)" if hidden else "")
            if row
            else "No relationship selected. Connect an entry to begin."
        )
        editable = (
            self._editable
            and row is not None
            and row.group != "References"
            and not hidden
        )
        self.edit_button.setEnabled(editable)
        self.remove_button.setEnabled(editable)
        self.go_button.setEnabled(row is not None and not hidden)
        for action, button in self._secondary_actions:
            action.setEnabled(button.isEnabled())
        self._fit_height()

    def _fit_height(self) -> None:
        # QSplitter uses minimumSizeHint, which omits QLabel height-for-width.
        # Reserve the actual wrapping layout height so rows cannot overlap.
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            self.setMinimumHeight(max(0, layout.minimumHeightForWidth(self.width())))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute intrinsic panel bounds after narrowing or text reflow."""
        super().resizeEvent(event)
        self._fit_height()

    def event(self, event: QEvent) -> bool:
        """Keep splitter bounds current when fonts or child labels relayout."""
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self._fit_height()
        return result

    def _activate(self, index: QModelIndex) -> None:
        if index.data(ROW_ROLE) == self.selected_id:
            self.edit_selected()

    def edit_selected(self) -> None:
        """Open only an explicitly selected, authored assertion."""
        row = self.selected_row()
        if row and self.edit_button.isEnabled():
            self.edit_requested.emit(row.snapshot)

    def remove_selected(self) -> None:
        """Request guarded removal at the inspector boundary."""
        row = self.selected_row()
        if row and self.remove_button.isEnabled() and self.before_selection():
            self.remove_requested.emit(row.snapshot)

    def navigate_selected(self) -> None:
        """Navigate through the existing inspector's cross-object draft guards."""
        row = self.selected_row()
        if row and self.go_button.isEnabled() and self.before_selection():
            self.navigate_requested.emit(row.other_id)

    def eventFilter(self, watched: Any, event: QEvent) -> bool:
        """Enter and Delete belong to the overview only while it has focus."""
        if (
            watched is self.tree.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            self._origin_focus = QApplication.focusWidget()
        if watched is self.tree and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    index = self.tree.currentIndex()
                    if index.data(ROW_ROLE + 1):
                        self.tree.setExpanded(index, not self.tree.isExpanded(index))
                    else:
                        self.edit_selected()
                    return True
                if event.key() == Qt.Key.Key_Delete:
                    if self.tree.currentIndex().data(ROW_ROLE) == self.selected_id:
                        self.remove_selected()
                    return True
        if watched is self.tree and event.type() == QEvent.Type.Resize:
            self.tree.scheduleDelayedItemsLayout()
        return super().eventFilter(watched, event)
