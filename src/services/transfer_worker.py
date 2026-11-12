"""Feature-owned transfer work, queued on the database-owning thread."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.entities import Entity
from src.core.events import Event
from src.core.transfer import EXCHANGE_VERSION, LORE_KINDS
from src.services.db_service import DatabaseService
from src.services.longform_builder import build_longform_sequence
from src.services.markdown_assets import copy_markdown_images, markdown_image_warnings
from src.services.obsidian_exporter import ObsidianExporter
from src.services.portable_note_links import note_name_candidates
from src.services.repositories.transfer_repository import lore_data, revision, snapshot
from src.services.transfer_context import export_context
from src.services.transfer_document import document_snapshot, write_docx, write_pdf
from src.services.transfer_exchange import (
    csv_text,
    fingerprint,
    load_sources,
    table_manifest,
)
from src.services.transfer_files import staged_markdown_output, staged_output
from src.services.transfer_import import prepare_import
from src.services.transfer_selection import select_lore
from src.services.world_transfer import export_world, import_world, inspect_package


class _SnapshotRecords:
    """Supply the existing note exporter with immutable captured lore."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def get_all_entities(self) -> list[Entity]:
        return [Entity.from_dict(row) for row in self.data["entities"]]

    def get_all_events(self) -> list[Event]:
        return [Event.from_dict(row) for row in self.data["events"]]

    def get_relations(self, item_id: str) -> list[dict[str, Any]]:
        return [row for row in self.data["relations"] if row["source_id"] == item_id]

    def get_all_calendar_configs(self) -> list[Any]:
        from src.core.calendar import CalendarConfig

        return [
            CalendarConfig.from_dict(row)
            for row in self.data.get("context", {}).get("calendars", [])
        ]


class TransferWorker(QObject):
    """Run feature operations without adding slots to DatabaseWorker."""

    finished = Signal(dict)

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Accept a getter invoked only from the owning worker thread."""
        super().__init__()
        self._database = database
        self.cancelled = threading.Event()

    @Slot(dict)
    def run(self, request: dict[str, Any]) -> None:
        """Dispatch one operation and return only serializable results."""
        result: dict[str, Any] = {
            "job_id": request["job_id"],
            "operation": request["operation"],
        }
        try:
            result.update(self._run(request))
            result["success"] = True
        except Exception as exc:
            result.update(success=False, error=str(exc))
        self.finished.emit(result)

    def _run(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request["operation"]
        if self.cancelled.is_set():
            raise InterruptedError("Transfer cancelled.")
        if operation == "load":
            return {"data": load_sources(request["sources"], request.get("pasted", ""))}
        if operation == "inspect_world":
            path = Path(request["path"])
            return {"package": inspect_package(path), "hash": fingerprint(str(path))}
        if operation == "import_world":
            path = Path(request["path"])
            if fingerprint(str(path)) != request["hash"]:
                raise ValueError("The world package changed. Review it again.")
            output = import_world(
                path,
                Path(request["worlds_root"]),
                request["name"],
                self.cancelled.is_set,
            )
            return {
                "path": str(output),
                "message": "World imported. Open it from Manage Worlds.",
            }
        db = self._database()
        if db is None or db.db_path != request["db_path"]:
            raise ValueError("The active world changed. Start the transfer again.")
        connection = db.get_connection()
        if connection is None:
            raise ValueError("No world is open.")
        if operation == "preview_import":
            return {"preview": prepare_import(db, request["data"], request["options"])}
        if operation == "prepare_export":
            return self._prepare_export(connection, request)
        if operation == "export":
            return self._export(connection, request)
        raise ValueError("Unknown transfer operation.")

    def _prepare_export(
        self, connection: sqlite3.Connection, request: dict[str, Any]
    ) -> dict[str, Any]:
        state = snapshot(connection)
        data = lore_data(state)
        selected = set(request.get("selected", []))
        warnings: list[str] = []
        if request.get("scope") == "selected":
            if not selected:
                raise ValueError("Select records in Explorer or choose All lore.")
            data, warnings, added = select_lore(
                data, selected, bool(request.get("include_endpoints"))
            )
            warnings.extend(
                f"Added dependency/endpoint: {identity}" for identity in added
            )
        db = self._database()
        assert db is not None
        context, context_warnings = export_context(db, data)
        data["context"] = context
        warnings.extend(context_warnings)
        result: dict[str, Any] = {
            "data": data,
            "revision": revision(state),
            "context_revision": self._context_revision(db),
            "warnings": warnings,
        }
        if request["format"] == "notes":
            result["note_name_candidates"] = note_name_candidates(
                (row["id"], row["name"])
                for kind in ("entities", "events")
                for row in state[kind]
            )
            world_path = request.get("world", {}).get("path", "")
            for record in [*data["entities"], *data["events"]]:
                warnings.extend(
                    markdown_image_warnings(
                        str(record.get("description", "")),
                        Path(world_path) if world_path else None,
                    )
                )
        if request["format"] in {"markdown", "pdf", "docx"}:
            sequence = build_longform_sequence(connection, include_unindexed=True)
            if not sequence:
                raise ValueError(
                    "The longform document is empty. Create world entries or restore "
                    "removed content in Longform."
                )
            result["document"] = document_snapshot(
                sequence, request["options"], request["world"].get("path", "")
            )
        return result

    @staticmethod
    def _context_revision(db: DatabaseService) -> str:
        from src.services.event_timing.planning import snapshot_fingerprint
        from src.services.event_timing.store import capture

        return snapshot_fingerprint(capture(db))

    def _export(
        self, connection: sqlite3.Connection, request: dict[str, Any]
    ) -> dict[str, Any]:
        destination = Path(request["destination"])
        key = request["format"]
        prepared = request["prepared"]
        db = self._database()
        if db is None or revision(snapshot(connection)) != prepared["revision"]:
            raise ValueError("World data changed. Review the export again.")
        if self._context_revision(db) != prepared.get("context_revision"):
            raise ValueError("Timing context changed. Review the export again.")
        world_path = request.get("world", {}).get("path", "")
        world_root = Path(world_path) if world_path else None
        if key == "markdown":
            with staged_markdown_output(
                destination, cancelled=self.cancelled.is_set
            ) as (output, images):
                content = copy_markdown_images(
                    prepared["document"]["markdown"],
                    world_root,
                    images,
                    destination.name + ".assets",
                    enabled=bool(request["options"].get("images", True)),
                )
                output.write_text(content, encoding="utf-8")
            return {"path": str(destination), "message": "Export complete."}
        if key == "world":
            if revision(snapshot(connection)) != prepared["revision"]:
                raise ValueError("World data changed. Review the export again.")
            export_world(
                connection, request["world"], destination, self.cancelled.is_set
            )
        else:
            data = prepared["data"]
            directory = key in {"csv", "notes"}
            with staged_output(
                destination, directory=directory, cancelled=self.cancelled.is_set
            ) as output:
                if key == "json":
                    output.write_text(
                        json.dumps(
                            {"exchange_version": EXCHANGE_VERSION, **data},
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                elif key == "csv":
                    (output / "manifest.json").write_text(
                        json.dumps(table_manifest(data), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    for kind in LORE_KINDS:
                        (output / f"{kind}.csv").write_text(
                            csv_text(kind, data[kind]), encoding="utf-8-sig"
                        )
                elif key == "notes":
                    note_result = ObsidianExporter(
                        _SnapshotRecords(data)
                    ).export_to_folder(
                        output, name_candidates=prepared.get("note_name_candidates")
                    )
                    if not note_result.success:
                        raise ValueError("\n".join(note_result.errors))
                    for note in output.glob("*.md"):
                        content = copy_markdown_images(
                            note.read_text(encoding="utf-8"),
                            world_root,
                            output / "assets",
                            "assets",
                        )
                        note.write_text(content, encoding="utf-8")
                elif key == "docx":
                    write_docx(prepared["document"], output)
                elif key == "pdf":
                    write_pdf(prepared["document"], output)
                else:
                    raise ValueError("Unsupported export format.")
        return {"path": str(destination), "message": "Export complete."}
