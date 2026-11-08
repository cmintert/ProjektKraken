"""Canonical saved map facts and date projections, without repository repair writes."""

import json
import math
from collections.abc import Callable
from dataclasses import asdict, fields
from typing import Any

from src.core.event_timing.solver import resolve_world
from src.core.feature_geometry_state import resolve_feature_geometry
from src.core.map import Map, MapLayerNode, resolve_layer_temporal_validity
from src.core.marker import MapFeature
from src.core.mcp_access import PAGE_SIZE, McpFailure
from src.core.trajectory import (
    apply_trajectory_metadata,
    interpolate_position,
    mfjson_to_keyframes,
)
from src.services.context_read_inputs import (
    _timing_references,
    checkpoint,
    timing_component_ids,
)
from src.services.db_service import DatabaseService
from src.services.mcp_image_variants import image_variants
from src.services.mcp_public import public_projection
from src.services.mcp_sections import section_page
from src.services.mcp_temporal import calendar_converter


def feature_at(db: DatabaseService, marker: MapFeature, day: float) -> dict[str, Any]:
    """Keep saved geometry separate from date-resolved geometry and its source."""
    if marker.is_path or marker.is_region:
        return {
            "geometry_evaluation": "at_lore_day",
            "resolved_geometry": asdict(
                resolve_feature_geometry(
                    marker, db.feature_geometry_repo.get_states(marker.id), day
                )
            ),
        }
    try:
        snapshot = db.get_marker_trajectory_snapshot(marker.map_id, marker.object_id)
        if snapshot is None:
            return {
                "position_evaluation": "saved_base",
                "position": [marker.x, marker.y],
            }
        frames = mfjson_to_keyframes(json.loads(snapshot["trajectory"]))
        frames, modes, _ = apply_trajectory_metadata(
            frames, json.loads(snapshot["properties"] or "{}")
        )
        return {
            "position_evaluation": "at_lore_day",
            "trajectory_id": snapshot["id"],
            "position": interpolate_position(
                frames, day, segment_modes=modes, base_position=(marker.x, marker.y)
            ),
        }
    except (ValueError, TypeError, KeyError, IndexError):
        return {"position_evaluation": "unresolved", "position": None}


def read_map_facts(
    db: DatabaseService, args: dict[str, Any], expired: Callable[[], bool]
) -> Any:
    """Read a map section independently of the UI selection and viewport."""
    item = db.get_map(str(args.get("map_id", "")))
    if item is None:
        raise McpFailure("NOT_FOUND")
    day, section = args.get("lore_day"), args.get("section")
    if day is not None and (type(day) not in {int, float} or not math.isfinite(day)):
        raise McpFailure("INVALID_DATE")
    if section == "description":
        return item.description
    if section == "images":
        return image_variants(item)
    if section == "metadata":
        return {
            "id": item.id,
            "name": item.name,
            "description_excerpt": item.description[:400],
            "description_length": len(item.description),
            "attributes": {
                key: value
                for key, value in item.attributes.items()
                if key not in {"raster_layers", "snapshots", "raster_snapshots"}
            },
            "image_variants": image_variants(item)[:PAGE_SIZE],
            "image_variants_complete": len(image_variants(item)) <= PAGE_SIZE,
            "image_available": bool(item.image_path),
        }
    anchors: dict[str, Any] = {}
    if day is not None and item.layers is not None:
        ids = timing_component_ids(
            db, _timing_references(item.layers.to_dict()), expired
        )
        events = [
            event for identifier in sorted(ids) if (event := db.get_event(identifier))
        ]
        anchors = resolve_world(events, calendar_converter(db), expired).anchors()
    if section == "layers":
        return _layers(db, item, day, anchors, expired)
    features = {"markers": "point", "paths": "path", "regions": "region"}
    if section not in features:
        raise McpFailure("INVALID_INPUT")
    rows = []
    markers = (
        db.get_markers_for_map(item.id)
        if "_feature_ids" not in args
        else [
            marker
            for identifier in args["_feature_ids"]
            if (marker := db.get_marker(identifier)) is not None
        ]
    )
    for marker in markers:
        checkpoint(expired)
        if marker.feature_type == features[section]:
            row = marker.to_dict()
            row["geometry_evaluation"] = "saved"
            if day is not None:
                row.update(feature_at(db, marker, day))
                row.update(_validity(db, item, marker.id, day, anchors))
            rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def feature_page(
    db: DatabaseService,
    args: dict[str, Any],
    expired: Callable[[], bool],
    offset: int,
    limit: int,
) -> tuple[dict[str, Any], int | None]:
    """Read only one map-feature candidate page, not every geometry on the map."""
    feature_type = {"markers": "point", "paths": "path", "regions": "region"}[
        args["section"]
    ]
    connection = db.require_connection()
    ids = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM markers WHERE map_id=? AND feature_type=? ORDER BY id LIMIT ? OFFSET ?",
            (args["map_id"], feature_type, limit + 1, offset),
        )
    ]
    rows = read_map_facts(db, {**args, "_feature_ids": ids[:limit]}, expired)
    data, _ = section_page(public_projection(rows), 0, limit)
    count = connection.execute(
        "SELECT count(*) FROM markers WHERE map_id=? AND feature_type=?",
        (args["map_id"], feature_type),
    ).fetchone()[0]
    until = offset + len(data["rows"])
    data.update(offset=offset, total_length=count)
    return data, until if until < count else None


def _validity(
    db: DatabaseService, item: Map, node_id: str, day: float, anchors: dict[str, Any]
) -> dict[str, Any]:
    if item.layers is None:
        return {}
    return {
        "temporal_validity": asdict(
            resolve_layer_temporal_validity(
                item.layers, node_id, day, calendar_converter(db), anchors=anchors
            )
        )
    }


def _layers(
    db: DatabaseService,
    item: Map,
    day: float | None,
    anchors: dict[str, Any],
    expired: Callable[[], bool],
) -> list[dict[str, Any]]:
    if item.layers is None:
        return []
    rows = []
    pending: list[tuple[MapLayerNode, str | None]] = [(item.layers, None)]
    while pending:
        checkpoint(expired)
        node, parent = pending.pop()
        row = {
            field.name: getattr(node, field.name)
            for field in fields(node)
            if field.name not in {"children", "virtual"}
        }
        row["parent_id"] = parent
        if day is not None:
            row.update(_validity(db, item, node.id, day, anchors))
        rows.append(row)
        pending.extend(
            (child, node.id) for child in reversed(node.children) if not child.virtual
        )
    return rows
