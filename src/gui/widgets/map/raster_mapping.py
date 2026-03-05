"""Value→Entity mapping helpers for raster layers.

Provides lookup functions that resolve raster cell values to entity
IDs using the ``value_entity_map`` metadata stored in each raster
layer's attributes.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Result of probing a single raster layer at a coordinate.

    Attributes:
        node_id: Layer node ID.
        value: Raw 16-bit value at the probed pixel.
        entity_id: Resolved entity ID (if mapped), or ``None``.
        label: Human-readable label from the mapping, or ``None``.
    """

    node_id: str
    value: int
    entity_id: Optional[str] = None
    label: Optional[str] = None


def lookup_entity_for_value(
    layer_meta: Dict[str, Any], value: int
) -> Optional[str]:
    """Resolve a raster value to an entity ID.

    Supports two mapping modes stored in
    ``layer_meta["value_entity_map"]``:

    * **exact** — each mapping has a single ``value`` key.
    * **range** — each mapping has ``min`` / ``max`` keys (inclusive).

    Args:
        layer_meta: A single raster layer metadata dict (from
            ``maps.attributes["raster_layers"]``).
        value: The 16-bit cell value to look up.

    Returns:
        Entity ID string, or ``None`` if no mapping matches.
    """
    vem = layer_meta.get("value_entity_map")
    if not vem:
        return None

    # Legacy flat dict format: {"1": "entity-uuid", ...}
    if isinstance(vem, dict) and "mappings" not in vem:
        return vem.get(str(value))

    # Structured format with mode
    mode = vem.get("mode", "exact")
    mappings: List[Dict[str, Any]] = vem.get("mappings", [])

    if mode == "exact":
        for m in mappings:
            if int(m.get("value", -1)) == value:
                return m.get("entity_id")

    elif mode == "range":
        for m in mappings:
            lo = int(m.get("min", 0))
            hi = int(m.get("max", 65535))
            if lo <= value <= hi:
                return m.get("entity_id")

    return None


def lookup_label_for_value(
    layer_meta: Dict[str, Any], value: int
) -> Optional[str]:
    """Resolve a raster value to a human-readable label.

    Args:
        layer_meta: Raster layer metadata dict.
        value: Cell value.

    Returns:
        Label string, or ``None``.
    """
    vem = layer_meta.get("value_entity_map")
    if not vem or not isinstance(vem, dict):
        return None

    mappings: List[Dict[str, Any]] = vem.get("mappings", [])
    mode = vem.get("mode", "exact")

    if mode == "exact":
        for m in mappings:
            if int(m.get("value", -1)) == value:
                return m.get("label")
    elif mode == "range":
        for m in mappings:
            lo = int(m.get("min", 0))
            hi = int(m.get("max", 65535))
            if lo <= value <= hi:
                return m.get("label")

    return None


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
        eid = lookup_entity_for_value(meta, val)
        label = lookup_label_for_value(meta, val)
        results.append(
            ProbeResult(
                node_id=node_id,
                value=val,
                entity_id=eid,
                label=label,
            )
        )
    return results
