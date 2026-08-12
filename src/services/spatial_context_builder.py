"""Spatial Context Builder Service.

Produces a qualitative, LLM-friendly description of an entity's or event's
placement on the active map. The output supplements the generation prompt
with grounded spatial information — which layer group a marker belongs to,
the raster-backed semantic class at the marker position (e.g. biome from a
terrain layer), nearby named features, and any layer-level annotations
authored by the user.

Design invariants
-----------------

* **Strict primary map.** The feature operates on the *currently active*
  map only. Multi-map entities never trigger a guessed fallback; when
  ``active_map_id`` is absent or does not contain the requested object,
  the builder returns ``None``.
* **Quality gate.** Sparse context backfires (LLMs fill gaps with
  training-data priors). The builder emits context only when at least
  one of (layer notes, raster semantic value, co-located named entity)
  is present; otherwise it returns ``None``.
* **Uncalibrated maps suppress distances.** A map without an explicit
  ``width_meters`` attribute reports relative proximity ("near",
  "further out") instead of kilometre figures — raw (x, y) coordinates
  are never emitted.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.core.map import Map, MapLayerNode, resolve_layer_temporal_validity
from src.core.map_constants import MAP_DEFAULT_WIDTH_METERS, MAP_ROLE_MASTER
from src.core.marker import Marker
from src.services.map_nesting_service import MapNestingService
from src.services.raster_image_analysis import sample_raster_semantic
from src.services.repositories.feature_geometry_repository import (
    FeatureGeometryRepository,
)
from src.services.repositories.map_repository import MapRepository

logger = logging.getLogger(__name__)

_MIN_LAYER_PATH_LENGTH = 2
_METRES_PER_KILOMETRE = 1000.0

_MAX_NEARBY = 5

# 8-point compass buckets for qualitative direction, ordered as the
# ``atan2`` result walks through them counter-clockwise from east.
_COMPASS_8 = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")

# Relative-proximity labels used when the map scale is uncalibrated.
# Bands are in normalised-coordinate Euclidean distance.
_PROXIMITY_BANDS: Tuple[Tuple[float, str], ...] = (
    (0.05, "adjacent to"),
    (0.15, "near"),
    (0.35, "in the broader vicinity of"),
    (1.5, "further out toward"),
)


NameLookup = Callable[[str, str], Optional[str]]
"""Callable that maps (object_id, object_type) → display name, or None."""


class SpatialContextBuilder:
    """Assemble a qualitative spatial context block for LLM prompts.

    The builder is constructed once per generation and queries the
    :class:`MapRepository` for marker and map data. Raster pixel sampling
    is performed via :func:`sample_raster_semantic` against absolute paths
    resolved beneath ``world_root``.
    """

    def __init__(
        self,
        map_repo: MapRepository,
        world_root: Optional[Path] = None,
        name_lookup: Optional[NameLookup] = None,
        nesting_service: Optional[MapNestingService] = None,
        feature_geometry_repo: Optional[FeatureGeometryRepository] = None,
    ) -> None:
        """Initialise the builder.

        Args:
            map_repo: Repository for map and marker access.
            world_root: Filesystem root of the active world, used to resolve
                relative raster ``file_path`` entries to absolute paths.
                When ``None``, raster sampling is skipped.
            name_lookup: Optional callable that resolves a co-located
                marker's linked object to a display name. When ``None`` or
                the callable returns ``None``, the builder falls back to
                ``Marker.label``.
            nesting_service: When provided, ``build()`` will append a
                ``Detail map available:`` advisory line when the marker
                position falls inside a registered child-map footprint.
                ``None`` (default) preserves existing behaviour exactly.
        """
        self._map_repo = map_repo
        self._world_root = Path(world_root) if world_root is not None else None
        self._name_lookup = name_lookup
        self._nesting_service = nesting_service
        self._feature_geometry_repo = feature_geometry_repo

    def build(
        self,
        object_id: str,
        object_type: str,
        active_map_id: Optional[str],
        lore_date: Optional[float] = None,
    ) -> Optional[str]:
        """Return a formatted spatial context string, or ``None`` if unavailable.

        Args:
            object_id: The entity or event being described.
            object_type: ``"entity"`` or ``"event"``.
            active_map_id: The currently selected map id, or ``None``. When
                ``None``, the builder returns ``None`` immediately — no
                fallback to "any map" is attempted.

        Returns:
            A newline-delimited ``[Spatial Context]`` block suitable for
            direct injection into the prompt, or ``None`` when no useful
            context could be assembled.
        """
        if not active_map_id or not object_id or not object_type:
            return None

        marker = self._map_repo.get_marker_by_composite(
            active_map_id, object_id, object_type
        )
        if marker is None:
            return None

        map_obj = self._map_repo.get_map(active_map_id)
        if map_obj is None:
            return None
        if not self._is_temporally_valid(map_obj, marker, lore_date):
            return None
        marker = self._resolve_marker_geometry(marker, lore_date)

        width_m = self._extract_width_meters(map_obj)
        suppress_distance = width_m is None

        layer_name, layer_notes = self._resolve_layer(map_obj, marker)
        raster_facts = self._resolve_raster_facts(map_obj, marker)
        nearby = self._resolve_nearby(
            map_obj, marker, width_m, suppress_distance, lore_date
        )

        has_notes = bool(layer_notes)
        has_raster = bool(raster_facts)
        has_nearby = bool(nearby)
        if not (has_notes or has_raster or has_nearby):
            return None

        context = self._format_context(
            map_name=map_obj.name,
            layer_name=layer_name,
            layer_notes=layer_notes,
            raster_facts=raster_facts,
            nearby=nearby,
        )

        advisory = self._resolve_detail_advisory(map_obj, marker)
        if advisory:
            context = context + "\n" + advisory

        return context

    # ------------------------------------------------------------------
    # Component resolvers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_width_meters(map_obj: Map) -> Optional[float]:
        """Return the map's real-world width in metres, or ``None`` if uncalibrated.

        A value equal to :data:`MAP_DEFAULT_WIDTH_METERS` is treated as
        uncalibrated — the application silently falls back to that value
        when the user never ran the scale-calibration dialog.
        """
        raw = (map_obj.attributes or {}).get("width_meters")
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        if math.isclose(value, MAP_DEFAULT_WIDTH_METERS):
            return None
        return value

    def _resolve_layer(
        self, map_obj: Map, marker: Marker
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve the marker's layer-group name and any annotation notes.

        Marker/path/region features are registered as leaf nodes in the
        :class:`MapLayerNode` tree with ``node.id == marker.id``. The
        meaningful "layer name" for humans is the leaf's parent group.
        Notes are collected from both the leaf node (feature-level) and
        its parent group (layer-level), concatenated if both present.
        """
        root = map_obj.layers
        if root is None:
            return None, None

        path = _find_path_to(root, marker.id)
        if not path:
            return None, None

        leaf = path[-1]
        parent = path[-2] if len(path) >= _MIN_LAYER_PATH_LENGTH else None
        layer_name = parent.name if parent is not None else leaf.name

        notes_parts: List[str] = []
        leaf_notes = str((leaf.attributes or {}).get("notes", "")).strip()
        if leaf_notes:
            notes_parts.append(leaf_notes)
        if parent is not None:
            parent_notes = str((parent.attributes or {}).get("notes", "")).strip()
            if parent_notes and parent_notes not in notes_parts:
                notes_parts.append(parent_notes)

        layer_notes = " | ".join(notes_parts) if notes_parts else None
        return layer_name, layer_notes

    def _resolve_raster_facts(
        self, map_obj: Map, marker: Marker
    ) -> List[Tuple[str, str, Optional[str]]]:
        """Sample every raster layer on this map at the marker position.

        Returns:
            List of ``(layer_name, label, notes)`` triples. Layers with
            empty VEMs, missing files, or no matching palette entry are
            omitted. ``notes`` is included for downstream consumers even
            when empty so the caller can decide whether to render it.
        """
        if self._world_root is None:
            return []
        raster_metas = (map_obj.attributes or {}).get("raster_layers") or []
        if not isinstance(raster_metas, list):
            return []

        facts: List[Tuple[str, str, Optional[str]]] = []
        for meta in raster_metas:
            if not isinstance(meta, dict):
                continue
            vem = meta.get("value_entity_map")
            if not isinstance(vem, dict) or not vem.get("mappings"):
                continue
            rel_path = meta.get("file_path")
            if not rel_path:
                continue
            abs_path = str(self._world_root / rel_path)

            label = sample_raster_semantic(abs_path, marker.x, marker.y, vem)
            if not label:
                continue

            layer_name = self._raster_layer_name(map_obj, meta) or "raster layer"
            notes = str(meta.get("notes", "")).strip() or None
            facts.append((layer_name, label, notes))
        return facts

    @staticmethod
    def _raster_layer_name(map_obj: Map, meta: dict) -> Optional[str]:
        """Look up a raster layer's display name via its ``node_id``."""
        node_id = meta.get("node_id")
        if not node_id or map_obj.layers is None:
            return None
        node = _find_node_by_id(map_obj.layers, node_id)
        return node.name if node is not None else None

    def _resolve_nearby(
        self,
        map_obj: Map,
        marker: Marker,
        width_m: Optional[float],
        suppress_distance: bool,
        lore_date: Optional[float] = None,
    ) -> List[Tuple[str, str]]:
        """Find up to :data:`_MAX_NEARBY` named markers on the same map.

        Returns:
            List of ``(name, relative_phrase)`` tuples, sorted by distance
            ascending. ``relative_phrase`` is either a qualitative label
            (e.g. ``"near"``) when the map is uncalibrated or a formatted
            distance with compass direction (e.g. ``"0.8 km NE"``).
        """
        all_markers = self._map_repo.get_markers_by_map(map_obj.id)
        if not all_markers:
            return []

        candidates: List[Tuple[float, Marker]] = []
        for other in all_markers:
            if other.id == marker.id:
                continue
            if other.object_id == marker.object_id and other.object_type == marker.object_type:
                continue
            if not self._is_temporally_valid(map_obj, other, lore_date):
                continue
            other = self._resolve_marker_geometry(other, lore_date)
            dx = other.x - marker.x
            dy = other.y - marker.y
            dist_norm = math.sqrt(dx * dx + dy * dy)
            candidates.append((dist_norm, other))

        candidates.sort(key=lambda pair: pair[0])

        results: List[Tuple[str, str]] = []
        for dist_norm, other in candidates:
            if len(results) >= _MAX_NEARBY:
                break
            name = self._lookup_name(other)
            if not name:
                continue
            phrase = self._format_relative_position(
                other.x - marker.x,
                other.y - marker.y,
                dist_norm,
                width_m,
                suppress_distance,
            )
            results.append((name, phrase))
        return results

    @staticmethod
    def _is_temporally_valid(
        map_obj: Map, marker: Marker, lore_date: Optional[float]
    ) -> bool:
        """Return historical map existence without applying presentation state."""
        if lore_date is None or map_obj.layers is None:
            return True
        return resolve_layer_temporal_validity(
            map_obj.layers, marker.id, lore_date
        ).valid

    def _resolve_marker_geometry(
        self, marker: Marker, lore_date: Optional[float]
    ) -> Marker:
        """Return a copy using its dated geometry anchor when requested."""
        if lore_date is None or self._feature_geometry_repo is None:
            return marker
        if not marker.is_path and not marker.is_region:
            return marker
        try:
            from dataclasses import replace

            from src.core.feature_geometry_state import resolve_feature_geometry

            resolved = resolve_feature_geometry(
                marker,
                self._feature_geometry_repo.get_states(marker.id),
                lore_date,
            )
            return replace(
                marker,
                x=resolved.anchor_x,
                y=resolved.anchor_y,
                geometry=resolved.geometry,
            )
        except Exception:
            logger.warning(
                "Could not resolve dated geometry for marker %s",
                marker.id,
                exc_info=True,
            )
            return marker

    def _lookup_name(self, marker: Marker) -> Optional[str]:
        """Resolve a marker's display name via injected lookup or ``label``."""
        if self._name_lookup is not None:
            try:
                resolved = self._name_lookup(marker.object_id, marker.object_type)
            except Exception:  # pragma: no cover - defensive
                logger.debug("name_lookup raised", exc_info=True)
                resolved = None
            if resolved:
                return resolved
        label = (marker.label or "").strip()
        return label or None

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_relative_position(
        dx: float,
        dy: float,
        dist_norm: float,
        width_m: Optional[float],
        suppress_distance: bool,
    ) -> str:
        """Render a single nearby marker's relative-position phrase."""
        direction = _compass_direction(dx, dy)
        if suppress_distance or width_m is None:
            proximity = _proximity_band(dist_norm)
            return f"{proximity} ({direction})"
        metres = dist_norm * width_m
        return f"{_format_distance(metres)} {direction}"

    @staticmethod
    def _format_context(
        map_name: str,
        layer_name: Optional[str],
        layer_notes: Optional[str],
        raster_facts: List[Tuple[str, str, Optional[str]]],
        nearby: List[Tuple[str, str]],
    ) -> str:
        """Produce the final ``[Spatial Context]`` block."""
        if layer_name:
            lead = f'Placed on map "{map_name}" in layer "{layer_name}".'
        else:
            lead = f'Placed on map "{map_name}".'

        lines: List[str] = ["[Spatial Context]", lead]
        if layer_notes:
            lines.append(f"- Layer notes: {layer_notes}")
        for layer, label, notes in raster_facts:
            if notes:
                lines.append(f"- {layer}: {label} ({notes})")
            else:
                lines.append(f"- {layer}: {label}")
        if nearby:
            pieces = ", ".join(f"{name} ({phrase})" for name, phrase in nearby)
            lines.append(f"- Nearby: {pieces}")
        return "\n".join(lines)


    def _resolve_detail_advisory(
        self, map_obj: Map, marker: Marker
    ) -> Optional[str]:
        """Return an advisory line if the marker falls inside a child footprint.

        Only fires when:
        * ``self._nesting_service`` is not ``None``.
        * The active map's role is ``MAP_ROLE_MASTER`` (Decision 5 — when
          a detail map is active, its own context wins; no advisory).
        * At least one registered child map's footprint contains the
          marker's normalised position.

        Args:
            map_obj: The active map.
            marker: The marker being described.

        Returns:
            A ``"Detail map available: <name>"`` line, or ``None``.

        """
        if self._nesting_service is None:
            return None
        role = (map_obj.attributes or {}).get("map_role")
        if role != MAP_ROLE_MASTER:
            return None
        try:
            all_maps = self._map_repo.get_all_maps()
        except Exception:
            return None
        children = MapRepository.get_children_of(map_obj.id, all_maps)
        for child in children:
            registration = (child.attributes or {}).get("registration")
            if registration is None:
                continue
            try:
                if self._nesting_service.point_in_footprint(
                    (marker.x, marker.y), registration
                ):
                    return f"Detail map available: {child.name}"
            except Exception:
                continue
        return None


# ---------------------------------------------------------------------------
# Module-level tree helpers (pure functions — easy to unit-test)
# ---------------------------------------------------------------------------


def _find_path_to(root: MapLayerNode, target_id: str) -> List[MapLayerNode]:
    """Return the ancestor→descendant path from *root* to the node with *target_id*.

    Returns an empty list when the node is not found.
    """

    def walk(node: MapLayerNode, trail: List[MapLayerNode]) -> List[MapLayerNode]:
        trail = trail + [node]
        if node.id == target_id:
            return trail
        for child in node.children:
            found = walk(child, trail)
            if found:
                return found
        return []

    return walk(root, [])


def _find_node_by_id(root: MapLayerNode, target_id: str) -> Optional[MapLayerNode]:
    """Locate a node by id anywhere in the tree."""
    if root.id == target_id:
        return root
    for child in root.children:
        found = _find_node_by_id(child, target_id)
        if found is not None:
            return found
    return None


def _compass_direction(dx: float, dy: float) -> str:
    """Map a normalised offset to an 8-point compass direction.

    The map's Y axis points downward (image convention), so *south*
    corresponds to ``dy > 0``.
    """
    if dx == 0.0 and dy == 0.0:
        return "here"
    # atan2 with inverted dy so that "up on screen" = north.
    angle = math.degrees(math.atan2(-dy, dx))
    # Shift so 0° aligns with East-NE boundary, then bucket into 45° slices.
    bucket = int(((angle + 22.5) % 360) // 45)
    return _COMPASS_8[bucket]


def _proximity_band(dist_norm: float) -> str:
    """Return a qualitative proximity label for a normalised distance."""
    for threshold, label in _PROXIMITY_BANDS:
        if dist_norm <= threshold:
            return label
    return _PROXIMITY_BANDS[-1][1]


def _format_distance(metres: float) -> str:
    """Format a distance in metres to a short, human-readable string."""
    if metres >= _METRES_PER_KILOMETRE:
        return f"{metres / _METRES_PER_KILOMETRE:.1f} km"
    return f"{int(round(metres))} m"


def lookup_spatial_context(
    db_path: str,
    object_id: str,
    object_type: str,
    active_map_id: str,
    lore_date: Optional[float] = None,
) -> Optional[str]:
    """Open a short-lived SQLite connection and build a spatial-context block.

    Shared by the GUI preview path and the background generation worker so
    both execute the exact same lookup. The connection is created locally
    (``check_same_thread=False``) so this helper is safe to call from any
    thread, including ``GenerationWorker``.

    Args:
        db_path: Absolute path to the world's ``.kraken`` SQLite file.
        object_id: UUID of the entity/event to look up.
        object_type: ``"entity"`` or ``"event"``.
        active_map_id: The currently selected map id.

    Returns:
        The formatted ``[Spatial Context]`` block, or ``None`` when the
        quality gate fails or an error is encountered.
    """
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            repo = MapRepository(conn)
            feature_geometry_repo = FeatureGeometryRepository(conn)
            builder = SpatialContextBuilder(
                repo,
                world_root=Path(db_path).parent,
                nesting_service=MapNestingService(),
                feature_geometry_repo=feature_geometry_repo,
            )
            return builder.build(
                object_id, object_type, active_map_id, lore_date
            )
        finally:
            conn.close()
    except Exception:
        logger.error("Spatial context lookup failed", exc_info=True)
        return None
