"""Read-only catalog for bundled and legacy marker icons."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.map_constants import DEFAULT_MARKER_ICONS_PATH
from src.core.marker_appearance import (
    MARKER_ICON_ATTRIBUTE,
    MARKER_ICON_ID_ATTRIBUTE,
)
from src.core.marker_icon import (
    DEFAULT_MARKER_ICON_ID,
    MarkerIconDefinition,
    MarkerIconSource,
)
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSettings,
    MarkerSizingSource,
)
from src.core.paths import get_resource_path
from src.services.asset_store import AssetStore

logger = logging.getLogger(__name__)

_MANIFEST_NAME = "manifest.json"


class MarkerIconCatalog:
    """Resolve icon definitions without mutating worlds or assets."""

    def __init__(self, definitions: list[MarkerIconDefinition]) -> None:
        """Index definitions by stable ID and normalized compatibility path."""
        self._definitions = tuple(definitions)
        self._by_id = {definition.id: definition for definition in definitions}
        self._by_path = {
            _normalize_path(definition.asset_path): definition
            for definition in definitions
        }

    @classmethod
    def load(cls, world_root: str | Path | None = None) -> "MarkerIconCatalog":
        """Load bundled metadata and synthesize missing legacy definitions."""
        definitions = _load_bundled_definitions()
        known_paths = {_normalize_path(item.asset_path) for item in definitions}
        default_root = Path(get_resource_path(DEFAULT_MARKER_ICONS_PATH))
        for asset in sorted(default_root.glob("*.svg")):
            if _normalize_path(asset.name) not in known_paths:
                definitions.append(_legacy_definition(asset.name, MarkerIconSource.DEFAULT))

        if world_root is not None:
            images_root = Path(world_root) / "assets" / "images"
            if images_root.is_dir():
                for asset in sorted(images_root.iterdir()):
                    if (
                        asset.is_file()
                        and asset.name.startswith("icon_")
                        and asset.suffix.lower() in AssetStore.ALLOWED_ICON_EXTENSIONS
                    ):
                        relative_path = asset.relative_to(Path(world_root)).as_posix()
                        definitions.append(
                            _legacy_definition(relative_path, MarkerIconSource.CUSTOM)
                        )
        return cls(definitions)

    @property
    def definitions(self) -> tuple[MarkerIconDefinition, ...]:
        """Return definitions in manifest/discovery order."""
        return self._definitions

    def defaults(self) -> tuple[MarkerIconDefinition, ...]:
        """Return bundled definitions."""
        return tuple(
            item for item in self._definitions if item.source is MarkerIconSource.DEFAULT
        )

    def custom(self) -> tuple[MarkerIconDefinition, ...]:
        """Return synthesized project-icon definitions."""
        return tuple(
            item for item in self._definitions if item.source is MarkerIconSource.CUSTOM
        )

    def resolve_id(self, icon_id: object) -> MarkerIconDefinition | None:
        """Resolve a stable ID when present."""
        return self._by_id.get(icon_id) if isinstance(icon_id, str) else None

    def resolve_path(self, asset_path: object) -> MarkerIconDefinition | None:
        """Resolve a bundled filename or portable-world relative path."""
        if not isinstance(asset_path, str) or not asset_path:
            return None
        return self._by_path.get(_normalize_path(asset_path))

    def resolve_attributes(self, attributes: dict) -> MarkerIconDefinition | None:
        """Resolve marker attributes by stable ID, then compatibility path."""
        return self.resolve_id(attributes.get(MARKER_ICON_ID_ATTRIBUTE)) or self.resolve_path(
            attributes.get(MARKER_ICON_ATTRIBUTE)
        )

    def default_definition(self) -> MarkerIconDefinition:
        """Return the standard map pin, with a safe catalog fallback."""
        definition = self.resolve_id(DEFAULT_MARKER_ICON_ID)
        if definition is not None:
            return definition
        if self._definitions:
            return self._definitions[0]
        return _legacy_definition("map-pin.svg", MarkerIconSource.DEFAULT)

    def new_marker_attributes(self, image_width: float) -> dict[str, object]:
        """Build canonical icon-default attributes for a new marker."""
        definition = self.default_definition()
        sizing = MarkerSizingSettings.for_map_image_width(
            image_width,
            native_diameter_px=definition.default_native_diameter_px,
        )
        return {
            MARKER_ICON_ID_ATTRIBUTE: definition.id,
            MARKER_ICON_ATTRIBUTE: definition.asset_path,
            MARKER_SIZING_ATTRIBUTE: sizing.to_dict(),
            MARKER_SIZING_SOURCE_ATTRIBUTE: MarkerSizingSource.ICON_DEFAULT.value,
        }


def _load_bundled_definitions() -> list[MarkerIconDefinition]:
    manifest_path = Path(get_resource_path(DEFAULT_MARKER_ICONS_PATH)) / _MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not load marker icon manifest: %s", manifest_path)
        return []
    if not isinstance(payload, dict) or payload.get("version") != 1:
        logger.warning("Unsupported marker icon manifest: %s", manifest_path)
        return []
    raw_icons = payload.get("icons")
    if not isinstance(raw_icons, list):
        logger.warning("Marker icon manifest has no icon list: %s", manifest_path)
        return []

    definitions: list[MarkerIconDefinition] = []
    seen_ids: set[str] = set()
    for raw_definition in raw_icons:
        if not isinstance(raw_definition, dict):
            continue
        try:
            definition = MarkerIconDefinition.from_dict(
                raw_definition,
                source=MarkerIconSource.DEFAULT,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid marker icon definition: %s", exc)
            continue
        if definition.id in seen_ids:
            logger.warning("Ignoring duplicate marker icon ID: %s", definition.id)
            continue
        seen_ids.add(definition.id)
        definitions.append(definition)
    return definitions


def _legacy_definition(
    asset_path: str,
    source: MarkerIconSource,
) -> MarkerIconDefinition:
    path = Path(asset_path)
    stem = path.stem.removeprefix("icon_")
    name = stem.replace("-", " ").replace("_", " ").strip().title() or "Icon"
    namespace = "default" if source is MarkerIconSource.DEFAULT else "custom"
    return MarkerIconDefinition(
        id=f"legacy.{namespace}.{path.stem.lower()}",
        name=name,
        asset_path=asset_path.replace("\\", "/"),
        source=source,
        category="Other" if source is MarkerIconSource.DEFAULT else "Project Icons",
    )


def _normalize_path(asset_path: str) -> str:
    return asset_path.replace("\\", "/").casefold()
