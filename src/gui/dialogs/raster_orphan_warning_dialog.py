"""Raster Orphan Warning Dialog.

Shown when the user deletes an entity that is referenced in one or more
raster layer ``value_entity_map`` entries.  Gives the user three options:
delete and remove the references, delete and leave the references, or cancel.
"""

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.map.raster_mapping import RasterItemRef


class RasterOrphanWarningDialog(QDialog):
    """Warning dialog shown when deleting an entity with raster layer references.

    Attributes:
        result_action: Set after ``exec()``; one of:
            ``"remove_and_delete"``, ``"delete_anyway"``, or ``"cancel"``.

    Args:
        entity_name: Display name (or ID) of the entity being deleted.
        refs: List of :class:`~src.gui.widgets.map.raster_mapping.RasterItemRef`
            instances that reference this entity.
        map_names: Mapping from map_id to human-readable map name.
        parent: Parent widget.
    """

    def __init__(
        self,
        entity_name: str,
        refs: List[RasterItemRef],
        map_names: Dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the orphaned-raster recovery dialog."""
        super().__init__(parent)
        self.setWindowTitle("Entity Has Raster References")
        self.setModal(True)
        self.setMinimumWidth(480)

        self.result_action: str = "cancel"

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Warning message
        msg = QLabel(
            f"<b>'{entity_name}'</b> is mapped in {len(refs)} raster layer(s)."
            "  Choose how to proceed:"
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # Reference list
        ref_list = QListWidget(self)
        for ref in refs:
            map_name = map_names.get(ref.map_id, ref.map_id)
            if ref.value is not None:
                val_str = f"value {ref.value}"
            elif ref.min is not None and ref.max is not None:
                val_str = f"range {ref.min}–{ref.max}"
            else:
                val_str = "range entry"
            label = ref.label or "(unlabelled)"
            ref_list.addItem(f"Map: {map_name} — Class: {label} ({val_str})")
        ref_list.setMaximumHeight(140)
        layout.addWidget(ref_list)

        # Buttons row
        btn_row = QHBoxLayout()

        self._btn_remove_and_delete = QPushButton("Delete + Remove refs")
        self._btn_remove_and_delete.setToolTip(
            "Delete the entity and remove its mapping from all raster layers"
        )
        self._btn_remove_and_delete.clicked.connect(self._on_remove_and_delete)
        btn_row.addWidget(self._btn_remove_and_delete)

        self._btn_delete_anyway = QPushButton("Delete anyway")
        self._btn_delete_anyway.setToolTip(
            "Delete the entity but leave the raster mappings as orphaned entries"
        )
        self._btn_delete_anyway.clicked.connect(self._on_delete_anyway)
        btn_row.addWidget(self._btn_delete_anyway)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_remove_and_delete(self) -> None:
        """Set action to remove_and_delete and close."""
        self.result_action = "remove_and_delete"
        self.accept()

    def _on_delete_anyway(self) -> None:
        """Set action to delete_anyway and close."""
        self.result_action = "delete_anyway"
        self.accept()

    def _on_cancel(self) -> None:
        """Set action to cancel and close."""
        self.result_action = "cancel"
        self.reject()
