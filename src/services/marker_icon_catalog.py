"""Read-only catalog for stable bundled and project marker icons."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.map_constants import DEFAULT_MARKER_ICONS_PATH
from src.core.marker_appearance import MARKER_ICON_ID_ATTRIBUTE
from src.core.marker_icon import (
    DEFAULT_MARKER_ICON_ID,
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
from src.core.paths import get_resource_path
from src.services.asset_store import AssetStore

logger = logging.getLogger(__name__)

_MANIFEST_NAME = "manifest.json"


class MarkerIconCatalog:
    """Resolve icon definitions without mutating worlds or assets."""

    def __init__(
        self,
        definitions: list[MarkerIconDefinition],
        *,
        default_root: Path,
        world_root: Path | None,
    ) -> None:
        """Index definitions by stable ID."""
        self._definitions = tuple(definitions)
        self._by_id = {definition.id: definition for definition in definitions}
        self._default_root = default_root
        self._world_root = world_root

    @classmethod
    def load(cls, world_root: str | Path | None = None) -> "MarkerIconCatalog":
        """Load manifest definitions and canonical imported project icons."""
        definitions = _load_bundled_definitions()
        default_root = Path(get_resource_path(DEFAULT_MARKER_ICONS_PATH))
        resolved_world_root = Path(world_root) if world_root is not None else None
        if resolved_world_root is not None:
            images_root = resolved_world_root / "assets" / "images"
            if images_root.is_dir():
                for asset in sorted(images_root.iterdir()):
                    if (
                        asset.is_file()
                        and asset.name.startswith("icon_")
                        and asset.suffix.lower() in AssetStore.ALLOWED_ICON_EXTENSIONS
                    ):
                        relative_path = asset.relative_to(resolved_world_root).as_posix()
                        icon_id = custom_icon_id_from_asset_path(relative_path)
                        if icon_id is not None:
                            definitions.append(
                                _custom_definition(icon_id, relative_path)
                            )
        return cls(
            definitions,
            default_root=default_root,
            world_root=resolved_world_root,
        )

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
        """Return canonical imported project-icon definitions."""
        return tuple(
            item for item in self._definitions if item.source is MarkerIconSource.CUSTOM
        )

    def resolve_id(self, icon_id: object) -> MarkerIconDefinition | None:
        """Resolve a stable ID when present."""
        return self._by_id.get(icon_id) if isinstance(icon_id, str) else None

    def resolve_attributes(self, attributes: dict) -> MarkerIconDefinition | None:
        """Resolve marker attributes exclusively by stable ID."""
        return self.resolve_id(attributes.get(MARKER_ICON_ID_ATTRIBUTE))

    def definition_or_default(self, icon_id: object) -> MarkerIconDefinition:
        """Resolve an icon ID or return the visible default definition."""
        definition = self.resolve_id(icon_id)
        if definition is not None:
            return definition
        if icon_id:
            logger.warning("Unknown marker icon ID: %s", icon_id)
        return self.default_definition()

    def asset_file(self, definition: MarkerIconDefinition) -> Path | None:
        """Return the trusted file path for one catalog definition."""
        if definition.source is MarkerIconSource.DEFAULT:
            return self._default_root / definition.asset_path
        if self._world_root is None:
            return None
        return self._world_root / definition.asset_path

    def default_definition(self) -> MarkerIconDefinition:
        """Return the required standard map-pin definition."""
        definition = self.resolve_id(DEFAULT_MARKER_ICON_ID)
        if definition is None:
            raise RuntimeError(
                f"Marker icon manifest must define {DEFAULT_MARKER_ICON_ID!r}"
            )
        return definition

    def new_marker_attributes(self, image_width: float) -> dict[str, object]:
        """Build canonical icon-default attributes for a new marker."""
        definition = self.default_definition()
        sizing = MarkerSizingSettings.for_map_image_width(
            image_width,
            native_diameter_px=definition.default_native_diameter_px,
        )
        return {
            MARKER_ICON_ID_ATTRIBUTE: definition.id,
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


def _custom_definition(icon_id: str, asset_path: str) -> MarkerIconDefinition:
    short_id = icon_id.removeprefix("custom.")[:8]
    return MarkerIconDefinition(
        id=icon_id,
        name=f"Project Icon {short_id}",
        asset_path=asset_path,
        source=MarkerIconSource.CUSTOM,
        category="Project Icons",
    )
