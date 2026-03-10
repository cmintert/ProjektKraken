"""Value→Entity mapping helpers for raster layers.

Provides data classes and lookup functions that resolve raster cell
values to entity/event IDs using the ``value_entity_map`` metadata
stored in each raster layer's attributes.

The canonical ``value_entity_map`` schema
-----------------------------------------

.. code-block:: json

    {
      "mode": "exact" | "range",
      "mappings": [
        {
          "id": "<uuid>",
          "label": "Temperate Forest",
          "entity_id": "<entity-or-event-uuid>",
          "item_type": "entity",
          "value": 42
        }
      ]
    }

This mirrors the GIS concept of a **Raster Attribute Table (RAT)**:
each discrete cell value maps to a class record with a stable identity,
a human-readable label, and an optional link to a world item (entity
or event).

Rules
~~~~~
* All ``id`` fields are stable UUIDs (used by undo/redo and the editor).
* Entries must be **mutually exclusive** — no two entries may cover the
  same value or overlapping ranges.  Use :func:`validate_no_overlaps`
  before persisting.
* ``mode`` is ``"exact"`` (each entry has a ``value`` key) or
  ``"range"`` (each entry has ``min``/``max`` keys, both inclusive).
* ``item_type`` is ``"entity"``, ``"event"``, or ``None``
  (unlinked/label-only entry).

Legacy formats are normalised transparently via
:func:`normalize_value_entity_map`.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical data classes
# ---------------------------------------------------------------------------


@dataclass
class RasterMappingEntry:
    """A single value-to-item record in a raster attribute table.

    Attributes:
        id: Stable UUID for undo/redo and editor references.
        label: Human-readable class name (e.g. ``"Temperate Forest"``).
        entity_id: Optional UUID of the linked entity or event.
        item_type: ``"entity"``, ``"event"``, or ``None``.
        value: Exact 16-bit cell value matched in ``"exact"`` mode.
        min: Minimum value (inclusive) for ``"range"`` mode.
        max: Maximum value (inclusive) for ``"range"`` mode.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    entity_id: Optional[str] = None
    item_type: Optional[str] = None
    value: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        d: Dict[str, Any] = {"id": self.id, "label": self.label}
        if self.entity_id is not None:
            d["entity_id"] = self.entity_id
        if self.item_type is not None:
            d["item_type"] = self.item_type
        if self.value is not None:
            d["value"] = self.value
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RasterMappingEntry":
        """Deserialise from a dict, assigning a fresh UUID if absent."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            label=data.get("label", ""),
            entity_id=data.get("entity_id"),
            item_type=data.get("item_type"),
            value=int(data["value"]) if "value" in data else None,
            min=int(data["min"]) if "min" in data else None,
            max=int(data["max"]) if "max" in data else None,
        )


@dataclass
class RasterValueEntityMap:
    """Raster attribute table (RAT) for a single raster layer.

    Attributes:
        mode: ``"exact"`` or ``"range"``.
        mappings: Mutually-exclusive list of :class:`RasterMappingEntry`.
    """

    mode: str = "exact"
    mappings: List[RasterMappingEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        return {
            "mode": self.mode,
            "mappings": [m.to_dict() for m in self.mappings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RasterValueEntityMap":
        """Deserialise from a dict."""
        return cls(
            mode=data.get("mode", "exact"),
            mappings=[
                RasterMappingEntry.from_dict(m) for m in data.get("mappings", [])
            ],
        )


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def make_empty_vem(mode: str = "exact") -> Dict[str, Any]:
    """Return a canonical empty ``value_entity_map`` dict.

    Args:
        mode: ``"exact"`` or ``"range"``.

    Returns:
        Dict ready to be stored in raster layer metadata.
    """
    return {"mode": mode, "mappings": []}


def normalize_value_entity_map(vem: Any) -> Dict[str, Any]:
    """Convert any legacy ``value_entity_map`` format to the canonical form.

    Handles three input formats transparently:

    1. **Empty / falsy** → returns a canonical empty ``"exact"`` map.
    2. **Legacy flat dict** ``{"1": "entity-uuid", ...}`` → converted to
       ``"exact"`` structured mappings with new stable UUIDs.
    3. **Structured dict** with ``"mappings"`` key → IDs are backfilled
       where absent; returned as-is otherwise.

    Args:
        vem: Raw value from ``layer_meta["value_entity_map"]``.

    Returns:
        Canonical dict with ``"mode"`` and ``"mappings"`` keys.
    """
    if not vem:
        return make_empty_vem()

    if not isinstance(vem, dict):
        logger.warning(
            "normalize_value_entity_map: unexpected type %s — resetting.",
            type(vem),
        )
        return make_empty_vem()

    # Already structured — just backfill missing IDs
    if "mappings" in vem:
        mode = vem.get("mode", "exact")
        normalized: List[Dict[str, Any]] = []
        for m in vem.get("mappings", []):
            entry = dict(m)
            if not entry.get("id"):
                entry["id"] = str(uuid.uuid4())
            normalized.append(entry)
        return {"mode": mode, "mappings": normalized}

    # Legacy flat dict: {"1": "entity-uuid", ...}
    logger.debug(
        "normalize_value_entity_map: converting legacy flat dict (%d entries).",
        len(vem),
    )
    mappings: List[Dict[str, Any]] = []
    for str_val, entity_id in vem.items():
        try:
            val = int(str_val)
        except (ValueError, TypeError):
            continue
        mappings.append(
            {
                "id": str(uuid.uuid4()),
                "value": val,
                "entity_id": entity_id if isinstance(entity_id, str) else None,
                "label": "",
            }
        )
    return {"mode": "exact", "mappings": mappings}


def validate_no_overlaps(vem: Dict[str, Any]) -> List[str]:
    """Validate that no two mapping entries cover the same value or range.

    Enforces the GIS best practice of mutually-exclusive classification
    classes in a raster attribute table.

    Args:
        vem: A canonical ``value_entity_map`` dict.

    Returns:
        A list of human-readable error strings.
        An empty list means the mapping is valid (no overlaps).
    """
    mode = vem.get("mode", "exact")
    mappings = vem.get("mappings", [])
    errors: List[str] = []

    intervals: List[tuple] = []
    for m in mappings:
        label = m.get("label") or str(m.get("value", m.get("min", "?")))
        if mode == "exact":
            v = m.get("value")
            if v is not None:
                intervals.append((int(v), int(v), label))
        else:
            lo = m.get("min")
            hi = m.get("max")
            if lo is not None and hi is not None:
                intervals.append((int(lo), int(hi), label))

    # Pairwise check — n is small for practical discrete raster maps
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            lo_i, hi_i, label_i = intervals[i]
            lo_j, hi_j, label_j = intervals[j]
            if lo_i <= hi_j and lo_j <= hi_i:
                errors.append(
                    f"Mapping '{label_i}' ({lo_i}–{hi_i}) overlaps "
                    f"'{label_j}' ({lo_j}–{hi_j})."
                )
    return errors


# ---------------------------------------------------------------------------
# Probe result
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Result of probing a single raster layer at a coordinate.

    Attributes:
        node_id: Layer node ID.
        value: Raw 16-bit value at the probed pixel.
        entity_id: Resolved entity/event ID (if mapped), or ``None``.
        item_type: ``"entity"``, ``"event"``, or ``None``.
        label: Human-readable label from the mapping, or ``None``.
    """

    node_id: str
    value: int
    entity_id: Optional[str] = None
    item_type: Optional[str] = None
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal lookup helper
# ---------------------------------------------------------------------------


def _find_matching_entry(vem: Dict[str, Any], value: int) -> Optional[Dict[str, Any]]:
    """Return the first mapping entry that matches *value*, or ``None``.

    Args:
        vem: Canonical ``value_entity_map`` dict.
        value: 16-bit cell value.

    Returns:
        Matching entry dict, or ``None``.
    """
    mode = vem.get("mode", "exact")
    for m in vem.get("mappings", []):
        if mode == "exact":
            v = m.get("value")
            if v is not None and int(v) == value:
                return m
        else:
            lo_v = m.get("min")
            hi_v = m.get("max")
            if lo_v is None or hi_v is None:
                continue
            if int(lo_v) <= value <= int(hi_v):
                return m
    return None


# ---------------------------------------------------------------------------
# Public lookup API
# ---------------------------------------------------------------------------


def lookup_entity_for_value(layer_meta: Dict[str, Any], value: int) -> Optional[str]:
    """Resolve a raster value to a linked entity or event ID.

    Supports legacy flat-dict format and the canonical structured format
    via transparent normalisation.

    Args:
        layer_meta: A single raster layer metadata dict from
            ``maps.attributes["raster_layers"]``.
        value: The 16-bit cell value to look up.

    Returns:
        Entity/event ID string, or ``None`` if no mapping matches.
    """
    raw = layer_meta.get("value_entity_map")
    if not raw:
        return None
    entry = _find_matching_entry(normalize_value_entity_map(raw), value)
    return entry.get("entity_id") if entry else None


def lookup_item_type_for_value(layer_meta: Dict[str, Any], value: int) -> Optional[str]:
    """Resolve a raster value to the linked item type.

    Args:
        layer_meta: Raster layer metadata dict.
        value: Cell value.

    Returns:
        ``"entity"``, ``"event"``, or ``None``.
    """
    raw = layer_meta.get("value_entity_map")
    if not raw:
        return None
    entry = _find_matching_entry(normalize_value_entity_map(raw), value)
    return entry.get("item_type") if entry else None


def lookup_label_for_value(layer_meta: Dict[str, Any], value: int) -> Optional[str]:
    """Resolve a raster value to a human-readable label.

    Args:
        layer_meta: Raster layer metadata dict.
        value: Cell value.

    Returns:
        Label string, or ``None``.
    """
    raw = layer_meta.get("value_entity_map")
    if not raw:
        return None
    entry = _find_matching_entry(normalize_value_entity_map(raw), value)
    return entry.get("label") if entry else None


def probe_all_layers(
    raster_items: Dict[str, Any],
    raster_meta_list: List[Dict[str, Any]],
    x_norm: float,
    y_norm: float,
) -> List[ProbeResult]:
    """Probe all active raster layers at a normalised coordinate.

    Args:
        raster_items: Mapping of ``node_id`` → ``RasterLayerItem``.
        raster_meta_list: The ``raster_layers`` metadata list from
            ``maps.attributes``.
        x_norm: Horizontal position [0, 1].
        y_norm: Vertical position [0, 1].

    Returns:
        List of :class:`ProbeResult`, one per visible raster layer.
    """
    meta_by_id: Dict[str, Dict[str, Any]] = {
        m["node_id"]: m for m in raster_meta_list if "node_id" in m
    }

    results: List[ProbeResult] = []
    for node_id, item in raster_items.items():
        if not item.isVisible():
            continue
        buf = item.buffer
        val = buf.get_value_at(x_norm, y_norm)
        meta = meta_by_id.get(node_id, {})
        entry = _find_matching_entry(
            normalize_value_entity_map(meta.get("value_entity_map") or {}), val
        )
        results.append(
            ProbeResult(
                node_id=node_id,
                value=val,
                entity_id=entry.get("entity_id") if entry else None,
                item_type=entry.get("item_type") if entry else None,
                label=entry.get("label") if entry else None,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Reverse index
# ---------------------------------------------------------------------------


@dataclass
class RasterItemRef:
    """A reference from a world item to a raster layer mapping.

    Produced by :func:`build_item_raster_index` as a lightweight record
    for item-centric queries: "on which maps does this entity/event appear
    via a raster classification?"

    Attributes:
        map_id: ID of the map that owns the raster layer.
        node_id: Raster layer node ID.
        mapping_id: Stable UUID of the mapping entry.
        label: Human-readable class label.
        mode: ``"exact"`` or ``"range"``.
        value: Exact cell value (exact mode).
        min: Minimum value, inclusive (range mode).
        max: Maximum value, inclusive (range mode).
    """

    map_id: str
    node_id: str
    mapping_id: str
    label: str = ""
    mode: str = "exact"
    value: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None


def build_item_raster_index(
    maps_data: List[Dict[str, Any]],
) -> Dict[str, List[RasterItemRef]]:
    """Build a reverse index from item IDs to their raster layer appearances.

    Scans all raster layer ``value_entity_map`` entries across all maps and
    returns a dict keyed by ``entity_id``.

    This enables item-centric queries such as "on which maps does entity X
    appear as a raster classification class?"

    Args:
        maps_data: List of map attribute dicts, each containing
            ``id`` and ``attributes["raster_layers"]``.

    Returns:
        Dict mapping ``entity_id`` → list of :class:`RasterItemRef`.
        Only entries with a non-empty ``entity_id`` are indexed.
    """
    index: Dict[str, List[RasterItemRef]] = {}

    for map_entry in maps_data:
        map_id = map_entry.get("id", "")
        raster_layers = (map_entry.get("attributes") or {}).get("raster_layers", [])
        for rl in raster_layers:
            node_id = rl.get("node_id", "")
            vem = normalize_value_entity_map(rl.get("value_entity_map") or {})
            mode = vem.get("mode", "exact")
            for m in vem.get("mappings", []):
                eid = m.get("entity_id")
                if not eid:
                    continue
                ref = RasterItemRef(
                    map_id=map_id,
                    node_id=node_id,
                    mapping_id=m.get("id", ""),
                    label=m.get("label", ""),
                    mode=mode,
                    value=m.get("value") if mode == "exact" else None,
                    min=m.get("min") if mode == "range" else None,
                    max=m.get("max") if mode == "range" else None,
                )
                index.setdefault(eid, []).append(ref)

    return index


def resolve_node_name(layers: Any, target_id: str) -> Optional[str]:
    """Walk a ``MapLayerNode`` tree to find a node's display name by ID.

    Args:
        layers: Root ``MapLayerNode`` instance (or ``None``).
        target_id: The node ID to search for.

    Returns:
        The node's ``name`` attribute, or ``None`` if not found.
    """
    if layers is None:
        return None
    if getattr(layers, "id", None) == target_id:
        return getattr(layers, "name", None)
    for child in getattr(layers, "children", []):
        result = resolve_node_name(child, target_id)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# UI helper — discrete class picker choices
# ---------------------------------------------------------------------------


def get_discrete_class_choices(
    layer_meta: Dict[str, Any],
    name_map: Optional[Dict[str, str]] = None,
) -> List[Tuple[str, int]]:
    """Return ``(display_label, value)`` pairs for a discrete class picker.

    Suitable for populating a *Paint as:* combo box.  Only returns entries
    that have an explicit ``value`` (i.e. ``mode == "exact"`` entries).

    Args:
        layer_meta: Raster layer metadata dict containing
            ``value_entity_map``.
        name_map: Optional dict mapping entity/event UUIDs to names.

    Returns:
        List of ``(display_label, value)`` tuples sorted ascending by
        value.  Empty if the layer has no defined classes.

    """
    vem_raw = layer_meta.get("value_entity_map", {})
    vem = normalize_value_entity_map(vem_raw)
    choices: List[Tuple[str, int]] = []
    for entry in vem.get("mappings", []):
        v = entry.get("value")
        if v is None:
            continue

        entity_id = entry.get("entity_id")

        # Precedence: Entity/Event Name > Label > UUID
        lbl = ""
        if entity_id and name_map and entity_id in name_map:
            lbl = name_map[entity_id]
        elif entry.get("label"):
            lbl = entry["label"]
        elif entity_id:
            lbl = entity_id
        else:
            lbl = f"Value {v}"

        choices.append((lbl, int(v)))
    return sorted(choices, key=lambda x: x[1])


def check_entity_raster_refs(
    entity_id: str,
    maps_data: List[Any],
) -> List[RasterItemRef]:
    """Find all raster layer mappings that reference the given entity.

    Scans the in-memory ``maps_data`` list (Map domain objects) for
    ``value_entity_map`` entries whose ``entity_id`` matches the
    supplied argument.

    Args:
        entity_id: The entity UUID to check.
        maps_data: List of Map domain objects with ``.id`` and
            ``.attributes`` attributes.

    Returns:
        List of :class:`RasterItemRef` instances referencing the entity.
        An empty list means no raster mappings reference this entity.
    """
    refs: List[RasterItemRef] = []
    for map_obj in maps_data:
        attrs = map_obj.attributes or {}
        raster_layers = attrs.get("raster_layers", [])
        for layer in raster_layers:
            node_id = layer.get("node_id", "")
            vem = normalize_value_entity_map(layer.get("value_entity_map") or {})
            mode = vem.get("mode", "exact")
            for m in vem.get("mappings", []):
                if m.get("entity_id") == entity_id:
                    ref = RasterItemRef(
                        map_id=map_obj.id,
                        node_id=node_id,
                        mapping_id=m.get("id", ""),
                        label=m.get("label", ""),
                        mode=mode,
                        value=m.get("value") if mode == "exact" else None,
                        min=m.get("min") if mode == "range" else None,
                        max=m.get("max") if mode == "range" else None,
                    )
                    refs.append(ref)
    return refs
