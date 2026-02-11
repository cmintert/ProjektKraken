"""Map Layer Panel Widget.

A themed panel that visualises the hierarchical layer tree and provides
controls for creating/deleting layers, adjusting opacity, renaming,
and reordering via drag-and-drop.  Integrates with the application's
:class:`StyleHelper` / :class:`ThemeManager` for consistent look and feel.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QModelIndex, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import (
    MAP_LAYER_DEFAULT_GROUP_NAME,
    MAP_LAYER_DEFAULT_OPACITY,
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
)
from src.core.map import MapLayerNode
from src.gui.utils.style_helper import StyleHelper

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)


class MapLayerPanel(QWidget):
    """Panel containing a QTreeView for the hierarchical layer system.

    Provides themed controls for:
    - Creating / deleting layer groups and leaf layers
    - Opacity adjustment via an inline slider
    - Renaming layers (double-click or context menu)
    - Drag-and-drop reordering
    - Bi-directional selection with the map view

    Signals:
        layer_selected: Emitted when a layer node is clicked.
            Payload is ``(node_id: str)``.
        create_group_requested: Emitted when the user wants a new group.
            Payload is ``(group_name: str)``.
        create_layer_requested: Emitted when the user wants a new leaf layer.
            Payload is ``(layer_name: str)``.
        delete_layer_requested: Emitted when the user wants to delete the
            currently selected layer.  Payload is ``(node_id: str)``.
        layer_opacity_changed: Emitted when opacity slider is moved.
            Payload is ``(node_id: str, opacity: float)``.
        layer_renamed: Emitted when a layer is renamed.
            Payload is ``(node_id: str, new_name: str)``.

    """

    layer_selected = Signal(str)
    create_group_requested = Signal(str)
    create_layer_requested = Signal(str)
    delete_layer_requested = Signal(str)
    layer_opacity_changed = Signal(str, float)
    layer_renamed = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the panel.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # ── Header ────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self._title_label = QLabel("Layers")
        self._title_label.setStyleSheet(StyleHelper.get_panel_header_style())
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        tool_style = StyleHelper.get_tool_button_style()

        self.btn_new_group = QPushButton("+ Group")
        self.btn_new_group.setToolTip("Create a new layer group")
        self.btn_new_group.setStyleSheet(tool_style)
        self.btn_new_group.clicked.connect(self._on_new_group)
        header_layout.addWidget(self.btn_new_group)

        self.btn_new_layer = QPushButton("+ Layer")
        self.btn_new_layer.setToolTip("Create a new layer")
        self.btn_new_layer.setStyleSheet(tool_style)
        self.btn_new_layer.clicked.connect(self._on_new_layer)
        header_layout.addWidget(self.btn_new_layer)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setToolTip("Delete the selected layer")
        self.btn_delete.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete)
        header_layout.addWidget(self.btn_delete)

        main_layout.addLayout(header_layout)

        # ── Tree View ─────────────────────────────────────────────────
        self._tree = QTreeView(self)
        self._tree.setHeaderHidden(True)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._tree.setAnimated(True)
        self._tree.setExpandsOnDoubleClick(False)  # double-click = rename
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.clicked.connect(self._on_item_clicked)
        self._tree.doubleClicked.connect(self._on_item_double_clicked)

        self._apply_tree_style()
        main_layout.addWidget(self._tree, 1)  # stretch=1 to fill space

        # ── Opacity Bar ───────────────────────────────────────────────
        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(4)

        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet(
            f"color: {self._theme_token('text_dim')}; font-size: 9pt;"
        )
        opacity_layout.addWidget(opacity_label)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setStyleSheet(StyleHelper.get_slider_style())
        self._opacity_slider.setToolTip("Layer opacity (0–100 %)")
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self._opacity_slider, 1)

        self._opacity_value_label = QLabel("100 %")
        self._opacity_value_label.setMinimumWidth(40)
        self._opacity_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._opacity_value_label.setStyleSheet(
            f"color: {self._theme_token('text_main')}; font-size: 9pt;"
        )
        opacity_layout.addWidget(self._opacity_value_label)

        main_layout.addLayout(opacity_layout)

        # ── Internal State ────────────────────────────────────────────
        self._model: Optional["MapLayerModel"] = None
        self._selected_node_id: Optional[str] = None
        self._slider_updating = False  # guard against feedback loops

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tree_view(self) -> QTreeView:
        """Access the underlying QTreeView."""
        return self._tree

    def set_model(self, model: "MapLayerModel") -> None:
        """Attach a :class:`MapLayerModel` to the tree view.

        Args:
            model: The layer model to display.

        """
        self._model = model
        self._tree.setModel(model)
        self._tree.expandAll()
        self._update_button_state()

    def select_node(self, node_id: str) -> None:
        """Highlight and scroll to the node with the given ID.

        Args:
            node_id: The layer node ID to select.

        """
        if self._model is None:
            return
        node = self._model.find_node_by_id(node_id)
        if node is None:
            return
        index = self._model.index_from_node(node)
        if index.isValid():
            self._tree.setCurrentIndex(index)
            self._tree.scrollTo(index)
            self._selected_node_id = node_id
            self._sync_opacity_slider(node)
            self._update_button_state()

    def refresh_styles(self) -> None:
        """Re-apply all theme-aware styles (call on theme change)."""
        tool_style = StyleHelper.get_tool_button_style()
        self.btn_new_group.setStyleSheet(tool_style)
        self.btn_new_layer.setStyleSheet(tool_style)
        self.btn_delete.setStyleSheet(StyleHelper.get_destructive_button_style())
        self._title_label.setStyleSheet(StyleHelper.get_panel_header_style())
        self._opacity_slider.setStyleSheet(StyleHelper.get_slider_style())
        self._apply_tree_style()

    # ------------------------------------------------------------------
    # Private — style helpers
    # ------------------------------------------------------------------

    def _apply_tree_style(self) -> None:
        """Apply the theme-aware stylesheet to the tree view."""
        self._tree.setStyleSheet(StyleHelper.get_tree_view_style())

    @staticmethod
    def _theme_token(key: str) -> str:
        """Fetch a single token from the current theme.

        Args:
            key: Theme token name (e.g. ``'text_dim'``).

        Returns:
            str: The hex colour for that token.

        """
        from src.core.theme_manager import ThemeManager

        return ThemeManager().get_theme().get(key, "#888888")

    # ------------------------------------------------------------------
    # Private — button actions
    # ------------------------------------------------------------------

    @Slot()
    def _on_new_group(self) -> None:
        """Prompt the user for a name and emit create_group_requested."""
        name, ok = QInputDialog.getText(
            self, "New Group", "Group name:", text="New Group"
        )
        if ok and name.strip():
            self.create_group_requested.emit(name.strip())

    @Slot()
    def _on_new_layer(self) -> None:
        """Prompt the user for a name and emit create_layer_requested."""
        name, ok = QInputDialog.getText(
            self, "New Layer", "Layer name:", text="New Layer"
        )
        if ok and name.strip():
            self.create_layer_requested.emit(name.strip())

    @Slot()
    def _on_delete(self) -> None:
        """Emit delete_layer_requested for the current selection."""
        if self._selected_node_id:
            self.delete_layer_requested.emit(self._selected_node_id)
            self._selected_node_id = None
            self._update_button_state()

    # ------------------------------------------------------------------
    # Private — tree interactions
    # ------------------------------------------------------------------

    @Slot(QModelIndex)
    def _on_item_clicked(self, index: QModelIndex) -> None:
        """Handle a click on a tree item.

        Args:
            index: The clicked model index.

        """
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(index)
        self._selected_node_id = node.id
        self._sync_opacity_slider(node)
        self._update_button_state()
        self.layer_selected.emit(node.id)

    @Slot(QModelIndex)
    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        """Handle double-click → rename.

        Args:
            index: The double-clicked model index.

        """
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(index)
        name, ok = QInputDialog.getText(
            self, "Rename Layer", "New name:", text=node.name
        )
        if ok and name.strip():
            self.layer_renamed.emit(node.id, name.strip())

    # ------------------------------------------------------------------
    # Private — context menu
    # ------------------------------------------------------------------

    @Slot()
    def _show_context_menu(self, pos) -> None:
        """Show a right-click context menu for the layer tree.

        Args:
            pos: Position of the click in widget coordinates.

        """
        index = self._tree.indexAt(pos)
        if self._model is None:
            return

        menu = QMenu(self)

        if index.isValid():
            node = self._model.node_from_index(index)
            self._selected_node_id = node.id
            self._sync_opacity_slider(node)
            self._update_button_state()

            # Toggle visibility
            vis_text = "Hide" if node.visible else "Show"
            action_toggle = menu.addAction(f"{vis_text} Layer")
            action_toggle.triggered.connect(
                lambda: self._toggle_visibility(node)
            )

            # Rename
            action_rename = menu.addAction("Rename…")
            action_rename.triggered.connect(
                lambda: self._on_item_double_clicked(index)
            )

            menu.addSeparator()

            # Delete
            action_delete = menu.addAction("Delete")
            action_delete.triggered.connect(self._on_delete)
        else:
            # Click on empty area — offer to create
            action_group = menu.addAction("New Group…")
            action_group.triggered.connect(self._on_new_group)
            action_layer = menu.addAction("New Layer…")
            action_layer.triggered.connect(self._on_new_layer)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _toggle_visibility(self, node: "MapLayerNode") -> None:
        """Toggle a node's visibility via the model.

        Args:
            node: The layer node to toggle.

        """
        if self._model is not None:
            self._model.set_node_visible(node, not node.visible)

    # ------------------------------------------------------------------
    # Private — opacity slider
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_opacity_changed(self, value: int) -> None:
        """Handle slider value change.

        Args:
            value: Slider value 0–100.

        """
        if self._slider_updating:
            return
        pct = value / 100.0
        self._opacity_value_label.setText(f"{value} %")
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                self._model.set_node_opacity(node, pct)
                self.layer_opacity_changed.emit(self._selected_node_id, pct)

    def _sync_opacity_slider(self, node: "MapLayerNode") -> None:
        """Update the slider to reflect the selected node's opacity.

        Args:
            node: The selected layer node.

        """
        self._slider_updating = True
        value = int(node.opacity * 100)
        self._opacity_slider.setValue(value)
        self._opacity_value_label.setText(f"{value} %")
        self._slider_updating = False

    # ------------------------------------------------------------------
    # Private — UI state
    # ------------------------------------------------------------------

    def _update_button_state(self) -> None:
        """Enable/disable the Delete button based on selection."""
        has_selection = self._selected_node_id is not None
        self.btn_delete.setEnabled(has_selection)
