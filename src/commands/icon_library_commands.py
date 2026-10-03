"""Worker-safe icon library requests and persistent undoable mutations."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.marker_icon import custom_icon_id_from_asset_path
from src.services.asset_store import AssetStore
from src.services.command_artifact_store import CommandArtifactStore
from src.services.db_service import DatabaseService
from src.services.icon_library_service import IconLibraryService


class IconLibraryCommand(BaseCommand):
    """Load, inspect, import, edit or remove custom icons on the database worker."""

    def __init__(
        self,
        world_root: str,
        world_id: str,
        operation: str = "load",
        *,
        icon_id: str = "",
        source_paths: list[str] | None = None,
        changes: dict[str, Any] | None = None,
    ) -> None:
        """Create a serializable intent without service or widget references."""
        super().__init__()
        if operation not in {"load", "usage", "import", "edit", "delete"}:
            raise ValueError("Unknown icon library operation")
        self.world_root = world_root
        self.world_id = world_id
        self.operation = operation
        self.icon_id = icon_id
        self.source_paths = list(source_paths or [])
        self.changes = copy.deepcopy(changes or {})
        self.protected: dict[str, list[str]] = {}
        self.before: dict[str, Any] | None = None
        self.after: dict[str, Any] | None = None
        self.document_existed = False
        self.added: list[dict[str, Any]] = []
        self.marker_changes: list[dict[str, Any]] = []
        self.artifact_manifest: dict[str, str] = {}
        self.report: dict[str, Any] = {}
        self._compensation: list[tuple[str, Any]] = []
        self._state_before: dict[str, Any] | None = None
        self._executed_before = False

    @property
    def is_undoable(self) -> bool:
        """Read requests and duplicate-only imports never enter history."""
        return self.operation in {"edit", "delete"} or (
            self.operation == "import" and bool(self.added)
        )

    def get_description(self) -> str:
        """Describe the library operation in undo history."""
        if self.operation == "import":
            return f"Import {len(self.added)} Project Icons"
        return f"{self.operation.title()} Project Icon"

    def _begin(self) -> None:
        self._state_before = self.to_dict()
        self._executed_before = self._is_executed
        self._compensation.clear()

    def _artifacts(self) -> CommandArtifactStore:
        store = CommandArtifactStore(Path(self.world_root))
        if not store.history_root.resolve().is_relative_to(store.world_root):
            raise ValueError("Icon history must remain inside the world")
        return store

    def _stash(self, paths: list[str]) -> None:
        if any(custom_icon_id_from_asset_path(path) is None for path in paths):
            raise ValueError("Only canonical icon artwork can be removed")
        self.artifact_manifest = self._artifacts().stash(self.command_id, paths)
        if len(self.artifact_manifest) != len(paths):
            self._compensation.append(("restore", dict(self.artifact_manifest)))
            raise FileNotFoundError("Icon artwork is missing; removal was cancelled")
        self._compensation.append(("restore", dict(self.artifact_manifest)))

    def _restore(self) -> None:
        store = self._artifacts()
        for target, artifact in self.artifact_manifest.items():
            if (
                custom_icon_id_from_asset_path(target) is None
                or artifact != f"assets/.history/{self.command_id}/{target}"
            ):
                raise ValueError("Invalid icon recovery manifest")
            if not store._world_path(artifact).is_file():
                raise FileNotFoundError("Icon recovery artwork is missing")
            if store._world_path(target).exists():
                raise FileExistsError("Cannot restore over existing icon artwork")
        store.restore(self.artifact_manifest)
        self._compensation.append(("stash", list(self.artifact_manifest)))

    def on_transaction_committed(self) -> None:
        """Release compensation only after the outer transaction commits."""
        self._compensation.clear()
        self._state_before = None

    def on_transaction_rolled_back(self) -> None:
        """Restore external files after failed results, exceptions or commit errors."""
        for operation, payload in reversed(self._compensation):
            if operation == "remove":
                Path(payload).unlink(missing_ok=True)
            elif operation == "restore":
                self._artifacts().restore(payload)
            elif operation == "stash":
                self._artifacts().stash(self.command_id, payload)
        self._compensation.clear()
        if self._state_before is not None:
            state = self.from_dict(self._state_before)
            for field in self._state_before:
                setattr(self, field, getattr(state, field))
            self._state_before = None
        self._is_executed = self._executed_before

    def _result(
        self, service: IconLibraryService, *, undo: bool = False
    ) -> CommandResult:
        return CommandResult(
            True,
            "Icon library updated",
            command_name=("Undo_IconLibraryCommand" if undo else "IconLibraryCommand"),
            data={
                "icon_library": service.snapshot(),
                "world_id": self.world_id,
                "world_root": self.world_root,
                "operation": self.operation,
                "report": self.report,
                "marker_attributes": [
                    {"id": m["id"], "attributes": m["attributes"]}
                    for m in service.repository.markers(self.icon_id)
                ]
                if self.icon_id
                else [],
                "map_ids": list(
                    dict.fromkeys(
                        [m["map_id"] for m in self.marker_changes]
                        + service.anchor_consumers(self.icon_id)
                    )
                ),
            },
        )

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute an intent or redo a captured operation without source files."""
        try:
            return self._execute(db_service)
        except (OSError, ValueError, RuntimeError) as exc:
            return CommandResult(
                False,
                str(exc),
                command_name="IconLibraryCommand",
                data={"world_id": self.world_id, "world_root": self.world_root},
            )

    def _execute(self, db_service: DatabaseService) -> CommandResult:
        self._begin()
        service = IconLibraryService(db_service, self.world_root)
        repo = service.repository
        if self.operation == "load":
            return self._result(service)
        if self.operation == "usage":
            self.report = {
                "usage": repo.usage(self.icon_id) + self.protected.get(self.icon_id, [])
            }
            return self._result(service)
        metadata = repo.read()
        if self.before is None:
            self.document_existed = repo.exists()
            self.before = copy.deepcopy(metadata)
            if self.operation == "import":
                self._import(service, metadata)
            elif self.operation == "edit":
                definition = service.custom_definition(self.icon_id)
                edited = service.edited_definition(definition, self.changes)
                self.marker_changes = service.default_size_changes(definition, edited)
                payload = dict(metadata.get(self.icon_id, {}))
                payload.update(edited.to_dict())
                payload["content_hash"] = service.digest(
                    service.contained_file(edited.asset_path)
                )
                metadata[self.icon_id] = payload
            else:
                definition = service.custom_definition(self.icon_id)
                service.require_unused([self.icon_id], self.protected)
                self._stash([definition.asset_path])
                metadata.pop(self.icon_id, None)
            self.after = copy.deepcopy(metadata)
        elif self.operation == "import":
            self._restore()
        elif self.operation == "delete":
            service.require_unused([self.icon_id], self.protected)
            self._stash(list(self.artifact_manifest))
        if self.operation != "import" or self.added:
            repo.write(copy.deepcopy(self.after or {}))
        for marker in self.marker_changes:
            repo.set_marker_fields(marker["id"], marker["after"])
        self._is_executed = True
        return self._result(service)

    def _import(self, service: IconLibraryService, metadata: dict[str, Any]) -> None:
        hashes: dict[str, str] = {}
        for definition in service.catalog().custom():
            path = service.contained_file(definition.asset_path)
            hashes.setdefault(service.digest(path), definition.id)
        report: dict[str, Any] = {"added": [], "reused": [], "failed": []}
        store = AssetStore(self.world_root)
        for source_path in self.source_paths:
            path = Path(source_path)
            target: Path | None = None
            try:
                service.validate_artwork(path)
                digest = service.digest(path)
                if digest in hashes:
                    report["reused"].append({"file": path.name, "id": hashes[digest]})
                    continue
                relative = store.import_icon(source_path)
                target = service.contained_file(relative)
                self._compensation.append(("remove", str(target)))
                service.validate_artwork(target)
                if service.digest(target) != digest:
                    raise ValueError("The source file changed during import; retry it")
                icon_id = custom_icon_id_from_asset_path(relative)
                assert icon_id is not None
                imported_definition: dict[str, Any] = {
                    "id": icon_id,
                    "name": path.stem,
                    "asset_path": relative,
                    "source": "custom",
                    "category": "Project Icons",
                    "default_native_diameter_px": 50.0,
                    "anchor": {"x": 0.5, "y": 0.5},
                    "source_filename": path.name,
                    "content_hash": digest,
                }
                metadata[icon_id] = imported_definition
                self.added.append(imported_definition)
                hashes[digest] = icon_id
                report["added"].append({"file": path.name, "id": icon_id})
            except (OSError, ValueError, RuntimeError) as exc:
                if target is not None:
                    target.unlink(missing_ok=True)
                report["failed"].append({"file": path.name, "error": str(exc)})
        self.report = report

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore original metadata, artwork and inherited marker fields."""
        try:
            return self._undo(db_service)
        except (OSError, ValueError, RuntimeError) as exc:
            return CommandResult(
                False,
                str(exc),
                command_name="Undo_IconLibraryCommand",
                data={"world_id": self.world_id, "world_root": self.world_root},
            )

    def _undo(self, db_service: DatabaseService) -> CommandResult:
        self._begin()
        service = IconLibraryService(db_service, self.world_root)
        if self.operation == "import":
            service.require_unused([d["id"] for d in self.added], self.protected)
            self._stash([d["asset_path"] for d in self.added])
        elif self.operation == "delete":
            self._restore()
        if self.document_existed:
            service.repository.write(copy.deepcopy(self.before or {}))
        else:
            service.repository.remove_document()
        for marker in self.marker_changes:
            service.repository.set_marker_fields(
                marker["id"], marker["before"], marker.get("before_missing", [])
            )
        self._is_executed = False
        return self._result(service, undo=True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize persistent state including recovery-bundle artifact references."""
        return copy.deepcopy(
            {
                field: getattr(self, field)
                for field in (
                    "world_root",
                    "world_id",
                    "operation",
                    "icon_id",
                    "source_paths",
                    "changes",
                    "protected",
                    "before",
                    "after",
                    "document_existed",
                    "added",
                    "marker_changes",
                    "artifact_manifest",
                    "report",
                )
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IconLibraryCommand:
        """Reconstruct command-owned snapshots for worker execution and restart."""
        command = cls(data["world_root"], data["world_id"], data["operation"])
        for field in command.to_dict():
            if field in data:
                setattr(command, field, copy.deepcopy(data[field]))
        return command
