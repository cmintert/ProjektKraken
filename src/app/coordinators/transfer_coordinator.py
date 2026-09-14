"""Feature-specific orchestration for unified transfer workflows."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from src.commands.transfer_commands import ApplyTransferCommand
from src.core.command import CommandResult
from src.core.paths import get_worlds_dir
from src.core.transfer import FORMAT_BY_KEY, LORE_KINDS, WORLD_TAB, lore_file_filter
from src.gui.dialogs.transfer_csv_dialog import TransferCsvDialog
from src.gui.dialogs.transfer_dialog import TransferDialog
from src.gui.models.explorer_model import ExplorerModel
from src.services.transfer_exchange import CSV_FIELDS, read_csv, template_text
from src.services.transfer_files import staged_output
from src.services.transfer_worker import TransferWorker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow
    from src.services.worker import DatabaseWorker

SAVE_WAIT_TIMEOUT_MS = 30_000


class TransferCoordinator(QObject):
    """Bind a narrow transfer view to worker jobs and the command pipeline."""

    requested = Signal(dict)

    def __init__(
        self,
        parent: QWidget,
        worker: DatabaseWorker,
        world_snapshot: Callable[[], dict[str, Any]],
        execute: Callable[[ApplyTransferCommand], None],
        flush: Callable[[], bool],
        refresh: Callable[[], None],
        selected: Callable[[], list[str]],
        specialists: dict[str, Callable[[], None]],
        saves_ready: Callable[[], bool] = lambda: True,
    ) -> None:
        """Connect narrow callbacks to the database-thread transfer adapter."""
        super().__init__(parent)
        self._parent = parent
        self._world_snapshot = world_snapshot
        self._execute = execute
        self._flush = flush
        self._refresh = refresh
        self._selected = selected
        self._specialists = specialists
        self._saves_ready = saves_ready
        self._waiting_for_saves = False
        self._save_error = ""
        self._save_clock = QElapsedTimer()
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(50)
        self._save_timer.timeout.connect(self._check_saves)
        self._worker = TransferWorker(lambda: worker.db_service)
        self._worker.moveToThread(worker.thread())
        worker.thread().finished.connect(self._worker.deleteLater)
        self.requested.connect(self._worker.run, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(
            self._finished, Qt.ConnectionType.QueuedConnection
        )
        worker.command_finished.connect(
            self._command_finished, Qt.ConnectionType.QueuedConnection
        )
        self.dialog: TransferDialog | None = None
        self._job = ""
        self._command_id = ""
        self._request: dict[str, Any] = {}
        self._world: dict[str, Any] = {}
        self._data: dict[str, Any] = {}
        self._preview: dict[str, Any] = {}
        self._prepared: dict[str, Any] = {}
        self._report = ""
        self._output = ""
        self._selection_override: list[str] | None = None

    def show(
        self, tab: int = 0, format_key: str = "", selected: list[str] | None = None
    ) -> None:
        """Open a modal workflow, preserving state when navigating between its steps."""
        if self.dialog is not None:
            self.dialog.raise_()
            return
        self._save_error = ""
        self._waiting_for_saves = True
        if not self._flush():
            self._waiting_for_saves = False
            return
        self._world = self._world_snapshot()
        self._selection_override = selected
        dialog = TransferDialog(self._parent)
        self.dialog = dialog
        dialog.context.setText(
            "World: " + self._world.get("manifest", {}).get("name", "Current world")
        )
        dialog.tabs.setCurrentIndex(tab)
        if format_key:
            dialog.export_format.setCurrentIndex(
                max(0, dialog.export_format.findData(format_key))
            )
        if selected:
            dialog.scope.setCurrentIndex(1)
        dialog.files_requested.connect(self._add_files)
        dialog.folder_requested.connect(self._add_folder)
        dialog.review_requested.connect(self._review)
        dialog.apply_requested.connect(self._apply)
        dialog.cancel_requested.connect(self._cancel)
        dialog.destination_requested.connect(self._choose_destination)
        dialog.package_requested.connect(self._choose_package)
        dialog.template_requested.connect(self._save_template)
        dialog.specialist_requested.connect(self._specialist)
        dialog.report_requested.connect(self._save_report)
        dialog.open_requested.connect(self._open_output)
        self._save_clock.start()
        dialog.set_busy(True, "Finishing pending editor saves…")
        self._save_timer.start()
        dialog.exec()
        self._save_timer.stop()
        self._waiting_for_saves = False
        self.dialog = None
        dialog.deleteLater()

    def _check_saves(self) -> None:
        if self.dialog is None:
            self._save_timer.stop()
            return
        if self._saves_ready() or self._save_error:
            self._save_timer.stop()
            self._waiting_for_saves = False
            self.dialog.set_busy(False, self._save_error)
        elif self._save_clock.elapsed() > SAVE_WAIT_TIMEOUT_MS:
            self._save_error = (
                "Editor saves have not finished. Close this window and resolve "
                "unsaved changes first."
            )
            self._check_saves()

    def _send(self, operation: str, **payload: Any) -> None:
        assert self.dialog is not None
        self._job = str(uuid.uuid4())
        self._worker.cancelled.clear()
        self.dialog.set_busy(True, "Working…")
        self.requested.emit(
            {
                "job_id": self._job,
                "operation": operation,
                "db_path": self._world.get("db_path", ""),
                **payload,
            }
        )

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self.dialog, "Choose lore files", "", lore_file_filter()
        )
        self._add_paths(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self.dialog, "Choose a lore folder")
        if folder:
            paths = sorted(
                str(path)
                for path in Path(folder).rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and path.suffix.lower() in {".json", ".md", ".csv", ".tsv"}
            )
            self._add_paths(paths)
            if not paths and self.dialog:
                self.dialog.status.setText(
                    "No supported lore files were found in that folder."
                )

    def _add_paths(self, paths: list[str]) -> None:
        assert self.dialog is not None
        sources = list(self.dialog.sources)
        for path in paths:
            if any(source["path"] == path for source in sources):
                continue
            source: dict[str, Any] = {"path": path}
            try:
                if Path(path).suffix.lower() in {".csv", ".tsv"}:
                    headers, rows = read_csv(path)
                    mapping = TransferCsvDialog(
                        path, headers, rows, CSV_FIELDS, self.dialog
                    )
                    if mapping.exec() != QDialog.DialogCode.Accepted:
                        continue
                    options = mapping.options()
                    targets = [value for value in options["mapping"].values() if value]
                    if len(targets) != len(set(targets)):
                        raise ValueError(
                            "Map each import field to only one CSV column."
                        )
                    source.update(options)
                sources.append(source)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self.dialog, "Input needs attention", str(exc))
        self.dialog.set_sources(sources)

    @Slot(dict)
    def _review(self, request: dict[str, Any]) -> None:
        assert self.dialog is not None
        self._request = request
        self.dialog.status.clear()
        try:
            if self._save_error:
                raise ValueError(self._save_error)
            if request["tab"] == 0:
                if request.get("recheck"):
                    edits = request["edits"]
                    for token, text in edits.items():
                        kind, index = token.split(":")
                        record = json.loads(text)
                        if not isinstance(record, dict):
                            raise ValueError("A record must be a JSON object.")
                        self._data[kind][int(index)] = record
                    self._send(
                        "preview_import",
                        data=self._data,
                        options=request["import_options"],
                    )
                else:
                    self._send(
                        "load", sources=request["sources"], pasted=request["pasted"]
                    )
            elif request["tab"] == 1:
                if not request["destination"]:
                    raise ValueError("Choose an export destination first.")
                self._send(
                    "prepare_export",
                    format=request["format"],
                    options=request["options"],
                    scope=request["scope"]
                    if request["format"] in {"json", "csv", "notes"}
                    else "all",
                    selected=self._selection_override or self._selected(),
                    include_endpoints=request["include_endpoints"],
                    world=self._world,
                )
            elif request["tab"] == WORLD_TAB:
                if not request["package_path"]:
                    raise ValueError(
                        "Choose a world package or output destination first."
                    )
                if request["world_mode"] == "import_world":
                    if not request["world_name"].strip():
                        raise ValueError("Enter a name for the new world.")
                    self._send("inspect_world", path=request["package_path"])
                else:
                    self._send(
                        "prepare_export",
                        format="world",
                        options={},
                        scope="all",
                        world=self._world,
                    )
        except (ValueError, OSError) as exc:
            self.dialog.status.setText(str(exc))

    @Slot(dict)
    def _finished(self, result: dict[str, Any]) -> None:
        dialog = self.dialog
        if dialog is None or result["job_id"] != self._job:
            return
        dialog.set_busy(False)
        if not result["success"]:
            dialog.status.setText(result["error"])
            return
        operation = result["operation"]
        if operation == "load":
            self._data = result["data"]
            self._send(
                "preview_import",
                data=self._data,
                options={"mode": self._request["mode"]},
            )
        elif operation == "preview_import":
            self._preview = result["preview"]
            dialog.show_import_review(self._data, self._preview)
        elif operation == "prepare_export":
            self._prepared = result
            document = result.get("document", {})
            warnings = result.get("warnings", []) + document.get("warnings", [])
            counts = ", ".join(
                f"{len(result['data'][kind])} {kind}" for kind in LORE_KINDS
            )
            destination = (
                self._request["destination"]
                if self._request["tab"] == 1
                else self._request["package_path"]
            )
            format_key = (
                self._request["format"] if self._request["tab"] == 1 else "world"
            )
            dialog.show_export_review(
                f"{FORMAT_BY_KEY[format_key].title}\nDestination: {destination}",
                counts
                + "\n"
                + FORMAT_BY_KEY[format_key].limitation
                + "\n"
                + "\n".join(warnings),
                document.get("html", ""),
            )
        elif operation == "inspect_world":
            self._prepared = result
            info = result["package"]
            dialog.show_export_review(
                "Import "
                f"'{info['manifest']['name']}' as "
                f"'{self._request['world_name']}'",
                f"{info['files']} files, {info['bytes']:,} bytes.\n"
                "Creates a new world folder; the active world is unchanged.",
            )
        elif operation in {"export", "import_world"}:
            self._output = result["path"]
            warnings = self._prepared.get("warnings", []) + self._prepared.get(
                "document", {}
            ).get("warnings", [])
            self._report = (
                result["message"] + "\n" + self._output + "\n" + "\n".join(warnings)
            )
            dialog.show_result(self._report, True, Path(self._output).is_dir())

    @Slot(dict)
    def _apply(self, request: dict[str, Any]) -> None:
        assert self.dialog is not None
        if request["tab"] == 0:
            command = ApplyTransferCommand(self._preview)
            self._command_id = command.command_id
            self.dialog.set_busy(True, "Applying reviewed changes atomically…")
            self._execute(command)
        elif request["tab"] == WORLD_TAB and request["world_mode"] == "import_world":
            self._send(
                "import_world",
                path=request["package_path"],
                hash=self._prepared["hash"],
                name=request["world_name"],
                worlds_root=str(get_worlds_dir()),
            )
        else:
            destination = (
                request["destination"]
                if request["tab"] == 1
                else request["package_path"]
            )
            if (
                Path(destination).exists()
                and QMessageBox.question(
                    self.dialog,
                    "Replace existing output?",
                    f"Replace this output?\n{destination}\n\n"
                    "The old output is retained if exporting fails.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            self._send(
                "export",
                destination=destination,
                format=request["format"] if request["tab"] == 1 else "world",
                prepared=self._prepared,
                world=self._world,
            )

    @Slot(object)
    def _command_finished(self, result: CommandResult) -> None:
        if self._waiting_for_saves and not result.success:
            self._save_error = "An editor save failed: " + result.message
        if (
            not self.dialog
            or result.data.get("transfer_id") != self._command_id
            or not self._command_id
        ):
            return
        self._command_id = ""
        self.dialog.set_busy(False)
        if not result.success:
            self.dialog.status.setText(result.message)
            return
        self._refresh()
        counts: dict[str, int] = {}
        for item in self._preview["delta"]:
            if item["table"] in LORE_KINDS:
                key = "Created" if item["before"] is None else "Changed"
                counts[key] = counts.get(key, 0) + 1
        self._report = (
            result.message
            + "\n"
            + "\n".join(f"{key}: {count}" for key, count in counts.items())
        )
        self._report += "\n" + "\n".join(self._preview.get("warnings", []))
        self._output = ""
        self.dialog.show_result(self._report, False, False)

    def _cancel(self) -> None:
        if self._waiting_for_saves:
            self._save_timer.stop()
            self._waiting_for_saves = False
            if self.dialog:
                self.dialog.set_busy(False)
                self.dialog.reject()
        elif self._command_id:
            if self.dialog:
                self.dialog.status.setText(
                    "Finishing the atomic import. You can undo it after completion."
                )
        else:
            self._worker.cancelled.set()

    def _choose_destination(self, key: str) -> None:
        assert self.dialog is not None
        if key in {"csv", "notes"}:
            folder = QFileDialog.getExistingDirectory(
                self.dialog, "Choose parent folder for export"
            )
            path = (
                str(Path(folder) / ("lore-tables" if key == "csv" else "lore-notes"))
                if folder
                else ""
            )
        else:
            item = FORMAT_BY_KEY[key]
            path, _ = QFileDialog.getSaveFileName(
                self.dialog,
                "Choose output",
                "export" + item.extensions[0],
                item.file_filter,
            )
            if path and not Path(path).suffix:
                path += item.extensions[0]
        if path:
            self.dialog.destination.setText(path)

    def _choose_package(self) -> None:
        assert self.dialog is not None
        item = FORMAT_BY_KEY["world"]
        if self.dialog.world_mode.currentData() == "import_world":
            path, _ = QFileDialog.getOpenFileName(
                self.dialog, "Choose portable world", "", item.file_filter
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self.dialog,
                "Export portable world",
                "world.krakenworld",
                item.file_filter,
            )
            if path and not Path(path).suffix:
                path += ".krakenworld"
        if path:
            self.dialog.package_path.setText(path)

    def _save_template(self, kind: str, key: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            "Save import example",
            f"{kind}.{key}",
            FORMAT_BY_KEY[key].file_filter,
        )
        if path:
            try:
                with staged_output(Path(path)) as output:
                    output.write_text(template_text(kind, key), encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self.dialog, "Could not save example", str(exc))

    def _save_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self.dialog, "Save transfer report", "transfer-report.txt", "Text (*.txt)"
        )
        if path:
            try:
                with staged_output(Path(path)) as output:
                    output.write_text(self._report, encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self.dialog, "Could not save report", str(exc))

    def _open_output(self, folder: bool) -> None:
        path = Path(self._output)
        if folder and path.is_file():
            path = path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _specialist(self, key: str) -> None:
        callback = self._specialists.get(key)
        if callback:
            callback()


def create_transfer_coordinator(window: MainWindow) -> TransferCoordinator:
    """Adapt the existing application facade to narrow feature dependencies."""

    def world_snapshot() -> dict[str, Any]:
        world = window.current_world
        return {
            "db_path": window.db_path,
            "path": str(world.path) if world else "",
            "manifest": world.manifest.to_dict() if world else {},
        }

    def flush() -> bool:
        for editor in (window.event_editor, window.entity_editor):
            if editor.has_unsaved_changes():
                editor._on_save()
        return True

    def selection() -> list[str]:
        view = window.unified_list.list_widget
        return [
            str(index.data(ExplorerModel.ItemIdRole))
            for index in view.selectionModel().selectedRows()
            if index.data(ExplorerModel.ItemIdRole)
        ]

    def show_panel(panel: str) -> None:
        window.workspace.show_panel(panel)
        if window.import_coordinator._transfer.dialog:
            window.import_coordinator._transfer.dialog.accept()

    def saves_ready() -> bool:
        editors = (window.event_editor, window.entity_editor)
        return (
            not window.command_coordinator._pending_commands
            and not any(editor.has_unsaved_changes() for editor in editors)
            and not window.command_coordinator._undo_redo_in_progress
        )

    return TransferCoordinator(
        window,
        window.worker,
        world_snapshot,
        window.command_coordinator.execute_command,
        flush,
        window.data_coordinator.load_data,
        selection,
        {
            "backup": window.backup_coordinator.create_manual_backup,
            "restore": window.backup_coordinator.restore_from_backup,
            "worlds": window.import_coordinator.show_database_manager,
            "map": window.map_widget._on_create_map_clicked,
            "raster": lambda: show_panel("map"),
            "gallery": lambda: show_panel("entity"),
            "analysis": lambda: show_panel("analysis"),
        },
        saves_ready,
    )
