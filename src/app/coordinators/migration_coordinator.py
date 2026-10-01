"""Present worker-owned migration outcomes and actionable recovery guidance."""

from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox, QWidget


class MigrationCoordinator(QObject):
    """Keep migration presentation independent of database and main-window logic."""

    def __init__(self, parent: QWidget, database_path: str) -> None:
        """Bind presentation to one startup database and dialog parent."""
        super().__init__(parent)
        self._dialog_parent = parent
        self._database_path = database_path
        self.last_report: dict[str, Any] = {}

    @Slot(dict)
    def on_report(self, report: dict[str, Any]) -> None:
        """Present failure recovery or an archived-undo notice on the GUI thread."""
        if report.get("database_path") != self._database_path:
            return
        self.last_report = dict(report)
        if report.get("success"):
            if report.get("history_archived"):
                QMessageBox.information(
                    self._dialog_parent,
                    "World upgraded",
                    "Your world was upgraded safely. Older undo history was "
                    "archived because relation formats changed. New edits have "
                    "a new undo history.\n\nRecovery bundle: "
                    f"{report.get('recovery_path')}",
                )
            return
        box = QMessageBox(self._dialog_parent)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("World upgrade blocked")
        box.setText("This world could not be opened for editing.")
        box.setInformativeText(str(report.get("message", "Migration failed")))
        recovery = report.get("recovery_path")
        details = (
            f"Database: {report.get('database_path')}\n"
            f"Failed step: {report.get('failed_step')}\n"
            f"Affected records: {', '.join(report.get('record_ids', [])) or 'none'}\n\n"
            "Editing is blocked. Preserve the world and its recovery files. "
            "Do not replace files while Kraken or "
            "another database client is running.\n"
        )
        if recovery:
            details += (
                f"Recovery directory: {recovery}\n"
                "A verified bundle contains recovery.json and database.kraken. "
                "If recovery.json is missing, this is an incomplete backup; "
                "do not restore it. Follow recovery.json to restore the database "
                "and command artifacts while Kraken is closed, then open with "
                "the previous compatible Kraken version."
            )
        else:
            details += (
                "No verified recovery bundle was created. Keep the original world "
                "and resolve the reported issue, or use a compatible Kraken version."
            )
        box.setDetailedText(details)
        box.exec()
