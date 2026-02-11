"""Map Layer Panel Widget.

A ``QTreeView``-based panel that visualises the hierarchical layer tree
and allows the user to toggle visibility, reorder layers via drag-and-drop,
and select layers for bi-directional highlight with the map view.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import (
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_REGION,
)

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)

# Phosphor-style unicode icons for layer types (LOW-11)
_LAYER_ICONS = {
    MAP_LAYER_TYPE_GROUP: "\U0001F4C2",  # 📂
    MAP_LAYER_TYPE_MARKER: "\U0001F4CD",  # 📍
    MAP_LAYER_TYPE_PATH: "\U00002935",   # ⤵
    MAP_LAYER_TYPE_REGION: "\U00002B1C",  # ⬜
}


class MapLayerPanel(QWidget):
    """Panel containing a QTreeView for the hierarchical layer system.

    Signals:
        layer_selected: Emitted when a layer node is clicked.
            Payload is ``(node_id: str)``.

    """

    layer_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the panel.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeView(self)
        self._tree.setHeaderHidden(True)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAnimated(True)
        self._tree.setExpandsOnDoubleClick(True)

        self._tree.clicked.connect(self._on_item_clicked)

        layout.addWidget(self._tree)

        self._model: Optional["MapLayerModel"] = None

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

    def select_node(self, node_id: str) -> None:
        """Highlight and scroll to the node with the given ID (LOW-10).

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

    def _on_item_clicked(self, index: QModelIndex) -> None:
        """Handle a click on a tree item.

        Args:
            index: The clicked model index.

        """
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(index)
        self.layer_selected.emit(node.id)
