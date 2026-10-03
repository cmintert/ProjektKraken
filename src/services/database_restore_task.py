"""Background execution for an already-quiesced database restore."""

from pathlib import Path

from PySide6.QtCore import QObject, QThread

from src.services.database_restore_service import DatabaseRestoreService, RestoreResult


class DatabaseRestoreTask(QThread):
    """Own only filesystem paths, never the live DatabaseService."""

    def __init__(
        self, backup: Path, target: Path, directory: Path, parent: QObject
    ) -> None:
        """Capture immutable restore inputs before starting the thread."""
        super().__init__(parent)
        self.backup = backup
        self.target = target
        self.directory = directory
        self.result: dict[str, bool | str] = RestoreResult().to_dict()

    def run(self) -> None:
        """Publish the result only after the thread has finished."""
        self.result = (
            DatabaseRestoreService()
            .restore(self.backup, self.target, self.directory)
            .to_dict()
        )
