"""Main-thread confirmation of worker-reported event anchor dependencies."""

from typing import Any

from PySide6.QtWidgets import QMessageBox, QWidget

from src.commands.event_commands import DeleteEventCommand


def confirm_temporal_deletion(
    data: dict[str, Any], parent: QWidget | None
) -> DeleteEventCommand | None:
    """Build a confirmed retry only after showing the actual dependency snapshot."""
    dependencies = data["temporal_dependencies"]
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("Delete an event used by chronology?")
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setText(
        f"{data['event_name']} anchors {len(dependencies)} temporal dependencies."
    )
    dialog.setInformativeText(
        "Attached relations will be removed. Other references will remain unresolved until the event is restored or their dates are changed. You can undo this deletion."
    )
    dialog.setDetailedText("\n".join(dependencies))
    dialog.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
    )
    dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
    if dialog.exec() != QMessageBox.StandardButton.Yes:
        return None
    return DeleteEventCommand(str(data["event_id"]), dependencies)
