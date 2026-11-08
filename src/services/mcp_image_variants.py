"""Stable saved raster identities; internal filenames never enter public results."""

from typing import Any

from src.core.map import Map
from src.core.map_state import RasterLayerState


def image_variants(item: Map) -> list[dict[str, Any]]:
    """Describe the base map and exact saved layer states without choosing a date."""
    result: list[dict[str, Any]] = [
        {
            "variant_id": "base",
            "lore_day": None,
            "layer_id": None,
            "_file": item.image_path,
        }
    ]
    for raw in item.attributes.get("raster_layers", []):
        state = RasterLayerState.from_dict(raw)
        prefix = "raster:" + state.node_id + ":"
        result.append(
            {
                "variant_id": prefix + "base",
                "layer_id": state.node_id,
                "lore_day": None,
                "_file": state.file_path,
            }
        )
        result.extend(
            {
                "variant_id": prefix + format(ref.lore_date, ".17g"),
                "layer_id": state.node_id,
                "lore_day": ref.lore_date,
                "_file": ref.file_path,
            }
            for ref in state.snapshots
        )
    return result
