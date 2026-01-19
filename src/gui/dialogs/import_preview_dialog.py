"""Import Preview Dialog.

Displays a preview of Entities, Events, and Relations to be imported from a JSON file.
"""

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.gui.utils.style_helper import StyleHelper


class ImportPreviewDialog(QDialog):
    """Dialog to preview and confirm import data."""

    def __init__(self, parent=None, parsed_data: Dict[str, List[Any]] = None) -> None:
        """Initialize the dialog.

        Args:
            parent: Parent widget.
            parsed_data: Dictionary with 'entities', 'events', 'relations' lists.
        """
        super().__init__(parent)
        self.parsed_data = parsed_data or {}
        self.setWindowTitle("Import Preview")
        self.resize(600, 500)

        self._init_ui()
        self._populate_tree()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Header
        header_lbl = QLabel("Review items to import:")
        header_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header_lbl)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Type", "Name / Details", "Status"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 300)
        layout.addWidget(self.tree)

        # Stats Label
        self.stats_lbl = QLabel("")
        layout.addWidget(self.stats_lbl)

        # Button Box
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(StyleHelper.get_dialog_base_style())

    def _populate_tree(self) -> None:
        """Populate the tree with parsed data."""
        self.tree.clear()

        # Entities
        entities = self.parsed_data.get("entities", [])
        if entities:
            root = QTreeWidgetItem(
                self.tree, ["Entities", f"{len(entities)} found", ""]
            )
            root.setExpanded(True)
            for ent in entities:
                name = ent.get("name", "<Missing Name>")
                type_ = ent.get("type", "generic")
                item = QTreeWidgetItem(root, [type_, name, "Ready"])
                # item.setIcon(0, StyleHelper.get_icon("cube"))  # Icon helper missing

        # Events
        events = self.parsed_data.get("events", [])
        if events:
            root = QTreeWidgetItem(self.tree, ["Events", f"{len(events)} found", ""])
            root.setExpanded(True)
            for evt in events:
                name = evt.get("name", "<Missing Name>")
                date = evt.get("lore_date", "?")
                item = QTreeWidgetItem(
                    root, ["Event", f"{name} (Date: {date})", "Ready"]
                )
                # item.setIcon(0, StyleHelper.get_icon("calendar"))  # Icon helper missing

        # Relations
        relations = self.parsed_data.get("relations", [])
        # Also count nested relations for stats
        nested_rel_count = 0
        for ent in entities:
            nested_rel_count += len(ent.get("relations", []))
        for evt in events:
            nested_rel_count += len(evt.get("relations", []))

        total_rels = len(relations) + nested_rel_count

        if total_rels > 0:
            root = QTreeWidgetItem(self.tree, ["Relations", f"{total_rels} found", ""])
            root.setExpanded(True)

            # Root relations
            for rel in relations:
                src = rel.get("source_name", rel.get("source_id", "?"))
                tgt = rel.get("target_name", rel.get("target_id", "?"))
                rel_type = rel.get("rel_type", "related")
                QTreeWidgetItem(
                    root, [rel_type, f"{src} -> {tgt}", "Pending Resolution"]
                )

            # Note: We don't list every nested relation to avoid clutter,
            # but we could if requested. For now, just root ones.
            if nested_rel_count > 0:
                QTreeWidgetItem(
                    root,
                    ["Nested", f"{nested_rel_count} nested relations", "Automatic"],
                )

        # Update stats
        self.stats_lbl.setText(
            f"Total: {len(entities)} Entities, {len(events)} Events, {total_rels} Relations"
        )
