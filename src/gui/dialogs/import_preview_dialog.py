"""Import Preview Dialog.

Displays a preview of Entities, Events, and Relations to be imported from a JSON file.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.gui.utils.style_helper import StyleHelper


class ImportPreviewDialog(QDialog):
    """Dialog to preview and confirm import data."""

    def __init__(
        self,
        parent: Optional[Any] = None,
        parsed_data: Optional[Dict[str, List[Any]]] = None,
    ) -> None:
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

        # Configuration Box
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout(config_group)

        # Row 1: Source and Mode
        row1 = QHBoxLayout()

        # Source Name
        row1.addWidget(QLabel("Source Name:"))
        self.source_edit = QLineEdit("manual_import")
        self.source_edit.setPlaceholderText("e.g. obsidian, world_anvil")
        row1.addWidget(self.source_edit)

        # Import Mode
        row1.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Update", "Overwrite", "Skip"])
        self.mode_combo.setToolTip(
            "Update: Merge new data into existing.\n"
            "Overwrite: Replace existing records completely.\n"
            "Skip: Ignore if record exists."
        )
        row1.addWidget(self.mode_combo)

        config_layout.addLayout(row1)

        # Row 2: Options
        self.dry_run_check = QCheckBox("Dry Run (Simulate only)")
        self.dry_run_check.setChecked(False)  # Default to real import? Or safe?
        # Let's verify defaults. Usually real run is expected after "Preview".
        config_layout.addWidget(self.dry_run_check)

        layout.addWidget(config_group)

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

        entities = self.parsed_data.get("entities", [])
        events = self.parsed_data.get("events", [])

        # Entities
        if entities:
            root = QTreeWidgetItem(
                self.tree, ["Entities", f"{len(entities)} found", ""]
            )
            root.setExpanded(True)
            for ent in entities:
                name = ent.get("name", "<Missing Name>")
                type_ = ent.get("type", "generic")
                _ = QTreeWidgetItem(root, [type_, name, "Ready"])

        # Events
        if events:
            root = QTreeWidgetItem(self.tree, ["Events", f"{len(events)} found", ""])
            root.setExpanded(True)
            for evt in events:
                name = evt.get("name", "<Missing Name>")
                date = evt.get("lore_date", "?")
                _ = QTreeWidgetItem(root, ["Event", f"{name} (Date: {date})", "Ready"])

        # Relations
        relations = self.parsed_data.get("relations", [])
        nested_rel_count = 0
        for ent in entities:
            nested_rel_count += len(ent.get("relations", []))
        for evt in events:
            nested_rel_count += len(evt.get("relations", []))

        total_rels = len(relations) + nested_rel_count

        if total_rels > 0:
            root = QTreeWidgetItem(self.tree, ["Relations", f"{total_rels} found", ""])
            root.setExpanded(True)

            for rel in relations:
                src = rel.get("source_name", rel.get("source_id", "?"))
                tgt = rel.get("target_name", rel.get("target_id", "?"))
                rel_type = rel.get("rel_type", "related")
                QTreeWidgetItem(
                    root, [rel_type, f"{src} -> {tgt}", "Pending Resolution"]
                )

            if nested_rel_count > 0:
                QTreeWidgetItem(
                    root,
                    ["Nested", f"{nested_rel_count} nested relations", "Automatic"],
                )

        # Conflicts: intra-file duplicate names
        conflicts = self._detect_intrafile_conflicts(entities, events)
        if conflicts:
            root = QTreeWidgetItem(
                self.tree, ["Conflicts", f"{len(conflicts)} found", "\u26a0 Review"]
            )
            root.setExpanded(True)
            for conflict in conflicts:
                QTreeWidgetItem(
                    root,
                    [
                        conflict["type"].title(),
                        f"\u26a0 Duplicate name: '{conflict['name']}' appears {conflict['count']} times",
                        "Will be skipped",
                    ],
                )

        # Update stats
        conflict_note = f", {len(conflicts)} conflicts" if conflicts else ""
        self.stats_lbl.setText(
            f"Total: {len(entities)} Entities, {len(events)} Events, "
            f"{total_rels} Relations{conflict_note}"
        )

    @staticmethod
    def _detect_intrafile_conflicts(
        entities: list, events: list
    ) -> list:
        """Detect items with duplicate normalized names within the import data.

        Args:
            entities: List of entity dicts from the parsed import.
            events: List of event dicts from the parsed import.

        Returns:
            List of conflict dicts with 'type', 'name', and 'count' keys.

        """
        from collections import Counter

        conflicts = []
        entity_names = [str(e.get("name", "")).strip().lower() for e in entities]
        for name, count in Counter(entity_names).items():
            if count > 1 and name:
                conflicts.append({"type": "entity", "name": name, "count": count})

        event_names = [str(e.get("name", "")).strip().lower() for e in events]
        for name, count in Counter(event_names).items():
            if count > 1 and name:
                conflicts.append({"type": "event", "name": name, "count": count})

        return conflicts

    def get_options(self) -> Dict[str, Any]:
        """Returns the configured import options."""
        return {
            "source_name": self.source_edit.text().strip() or "manual_import",
            "mode": self.mode_combo.currentText().lower(),
            "dry_run": self.dry_run_check.isChecked(),
        }
