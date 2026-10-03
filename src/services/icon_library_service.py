"""Custom icon validation, catalog snapshots, and inherited marker defaults."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtGui import QImageReader
from PySide6.QtSvg import QSvgRenderer

from src.core.marker_appearance import MARKER_ICON_ANCHOR_ATTRIBUTE
from src.core.marker_icon import (
    MarkerIconDefinition,
    MarkerIconSource,
    custom_icon_id_from_asset_path,
)
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSettings,
    MarkerSizingSource,
)
from src.services.asset_store import AssetStore
from src.services.db_service import DatabaseService
from src.services.marker_icon_catalog import MarkerIconCatalog
from src.services.repositories.icon_library_repository import IconLibraryRepository


class IconLibraryService:
    """Operate on the worker-owned database and the actual portable asset root."""

    def __init__(self, db: DatabaseService, world_root: str) -> None:
        """Reject requests targeting a different world's asset directory."""
        self.root = Path(world_root).resolve()
        expected = db.world_root or Path(db.get_db_file_path()).resolve().parent
        if self.root != Path(expected).resolve():
            raise ValueError("Icon request belongs to a different world")
        self.repository = IconLibraryRepository(db.require_connection())

    def catalog(self) -> MarkerIconCatalog:
        """Load immutable definitions using persisted custom metadata."""
        return MarkerIconCatalog.load(self.root, self.repository.read())

    def snapshot(self) -> dict[str, Any]:
        """Return a GUI-safe library snapshot without writing to disk."""
        metadata = self.repository.read()
        catalog = MarkerIconCatalog.load(self.root, metadata)
        return {"metadata": metadata, "icons": [d.to_dict() for d in catalog.custom()]}

    def custom_definition(self, icon_id: str) -> MarkerIconDefinition:
        """Resolve an editable canonical custom icon."""
        definition = self.catalog().resolve_id(icon_id)
        if definition is None or definition.source is not MarkerIconSource.CUSTOM:
            raise ValueError("Only existing project icons can be edited or deleted")
        self.contained_file(definition.asset_path)
        return definition

    def contained_file(self, asset_path: str) -> Path:
        """Resolve canonical artwork without following links outside the world."""
        if custom_icon_id_from_asset_path(asset_path) is None:
            raise ValueError("Invalid custom icon asset path")
        path = (self.root / asset_path).resolve()
        images = (self.root / "assets" / "images").resolve()
        if not images.is_relative_to(self.root) or not path.is_relative_to(images):
            raise ValueError("Icon artwork must remain inside world assets")
        return path

    @staticmethod
    def digest(path: Path) -> str:
        """Hash original artwork bytes for exact duplicate reuse."""
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    @staticmethod
    def validate_artwork(path: Path) -> None:
        """Reject unsupported or unreadable SVG and raster artwork."""
        if path.suffix.lower() not in AssetStore.ALLOWED_ICON_EXTENSIONS:
            raise ValueError("Choose an SVG, PNG, JPEG, or WebP file")
        if path.suffix.lower() == ".svg":
            renderer = QSvgRenderer(str(path))
            if not renderer.isValid() or renderer.defaultSize().isEmpty():
                raise ValueError("The SVG artwork cannot be read")
        else:
            with Image.open(path) as image:
                image.verify()

    @staticmethod
    def edited_definition(
        definition: MarkerIconDefinition, changes: dict[str, Any]
    ) -> MarkerIconDefinition:
        """Validate editable fields without changing stable identity."""
        payload = definition.to_dict()
        allowed = {"name", "category", "default_native_diameter_px", "anchor"}
        if set(changes) - allowed:
            raise ValueError("Icon identity and artwork cannot be changed")
        payload.update(changes)
        diameter = float(payload["default_native_diameter_px"])
        anchor = payload["anchor"]
        if not math.isfinite(diameter) or diameter <= 0:
            raise ValueError("Native diameter must be a positive finite number")
        if not isinstance(anchor, dict) or any(
            not math.isfinite(float(anchor.get(axis, -1)))
            or not 0 <= float(anchor.get(axis, -1)) <= 1
            for axis in ("x", "y")
        ):
            raise ValueError("Anchor coordinates must be between 0 and 1")
        return MarkerIconDefinition.from_dict(payload, source=MarkerIconSource.CUSTOM)

    def default_size_changes(
        self, before: MarkerIconDefinition, after: MarkerIconDefinition
    ) -> list[dict[str, Any]]:
        """Snapshot inherited sizes across all maps before editing a default."""
        result: list[dict[str, Any]] = []
        if before.default_native_diameter_px == after.default_native_diameter_px:
            return result
        widths: dict[str, int] = {}
        for marker in self.repository.markers(before.id):
            attrs = marker["attributes"]
            if attrs.get(MARKER_SIZING_SOURCE_ATTRIBUTE) != (
                MarkerSizingSource.ICON_DEFAULT.value
            ):
                continue
            map_id = marker["map_id"]
            if map_id not in widths:
                image = Path(marker["image_path"])
                if not image.is_absolute():
                    image = self.root / image
                reader = QImageReader(str(image))
                width = reader.size().width()
                if width <= 0 or not reader.canRead():
                    raise ValueError(
                        f"Cannot update icon size: map '{marker['map_name']}' "
                        "has an unreadable image. Restore its image first."
                    )
                widths[map_id] = width
            settings = MarkerSizingSettings.for_map_image_width(
                widths[map_id], after.default_native_diameter_px
            )
            result.append(
                {
                    "id": marker["id"],
                    "map_id": map_id,
                    "before": {
                        MARKER_SIZING_ATTRIBUTE: attrs.get(MARKER_SIZING_ATTRIBUTE)
                    },
                    "before_missing": (
                        [MARKER_SIZING_ATTRIBUTE]
                        if MARKER_SIZING_ATTRIBUTE not in attrs
                        else []
                    ),
                    "after": {MARKER_SIZING_ATTRIBUTE: settings.to_dict()},
                }
            )
        return result

    def require_unused(
        self, icon_ids: list[str], protected: dict[str, list[str]]
    ) -> None:
        """Recheck persisted references and registered editor drafts."""
        uses = []
        for icon_id in icon_ids:
            uses.extend(self.repository.usage(icon_id))
            uses.extend(protected.get(icon_id, []))
        if uses:
            raise ValueError("Icon is in use:\n" + "\n".join(dict.fromkeys(uses)))

    def anchor_consumers(self, icon_id: str) -> list[str]:
        """Identify maps inheriting anchor metadata for view refresh."""
        return list(
            dict.fromkeys(
                marker["map_id"]
                for marker in self.repository.markers(icon_id)
                if MARKER_ICON_ANCHOR_ATTRIBUTE not in marker["attributes"]
            )
        )
