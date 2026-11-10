"""Completion presentation for undoable removals outside the Explorer refresh."""

from PySide6.QtWidgets import QWidget

from src.core.command import CommandResult, parse_lore_mutation_effects
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox

_DELETION_LABELS = {
    "DeleteEventCommand": "Event",
    "DeleteEntityCommand": "Entity",
    "DeleteMapCommand": "map",
    "DeleteMarkerCommand": "marker",
    "DeleteLayerSubtreeCommand": "layer",
    "DeleteRasterLayerCommand": "raster layer",
    "RemoveRasterSnapshotCommand": "raster snapshot",
    "DeleteCalendarConfigCommand": "calendar configuration",
    "RemoveRelationCommand": "relation",
}


def present_deletion_feedback(result: CommandResult, parent: object) -> None:
    """Report accepted deletion results; never infer success from intent.

    Lore effects already produce a named Explorer notification. Undo/redo,
    failures, and unrelated commands do not match these ordinary action names.
    Removing Longform membership retains the world entry and says Removed.
    """
    if not result.success or not isinstance(parent, QWidget):
        return
    effects = parse_lore_mutation_effects(result.data.get("lore_effects"))
    if effects and any(effect["operation"] == "delete" for effect in effects):
        return
    if result.command_name == "RemoveLongformEntryCommand":
        title, text = "Removed", "Removed entry from this document."
    elif result.command_name in _DELETION_LABELS:
        title = "Deleted"
        text = f"Deleted {_DELETION_LABELS[result.command_name]}."
    else:
        return
    AutoClosingMessageBox.notify(parent, title, text + "\n\nUndo with Ctrl+Z.")
