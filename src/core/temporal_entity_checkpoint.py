"""Serializable comparison checkpoints for acknowledged temporal entity saves."""

import json
from copy import deepcopy
from math import isfinite
from typing import Any, TypedDict, cast


class TemporalEntityCheckpoint(TypedDict):
    """State and baseline metadata observed within a successful save transaction."""

    entity_id: str
    lore_time: float
    state: dict[str, Any]
    baseline_metadata: dict[str, Any]


def parse_temporal_entity_checkpoint(
    value: object, entity_id: str, lore_time: float
) -> TemporalEntityCheckpoint | None:
    """Validate delivery context and required comparison fields; return a copy."""
    if not isinstance(value, dict) or value.get("entity_id") != entity_id:
        return None
    time = value.get("lore_time")
    if (
        not isinstance(time, (int, float))
        or isinstance(time, bool)
        or not isfinite(time)
        or time != lore_time
    ):
        return None
    state = value.get("state")
    metadata = value.get("baseline_metadata")
    if not isinstance(state, dict) or not isinstance(metadata, dict):
        return None
    if state.get("entity_id") != entity_id or not isinstance(
        state.get("description"), str
    ):
        return None
    for key in ("attributes", "attribute_sources", "absent_attribute_sources"):
        if not isinstance(state.get(key), dict):
            return None
    sources = [state.get("description_source")]
    sources.extend(state["attribute_sources"].values())
    sources.extend(state["absent_attribute_sources"].values())
    if any(not _valid_source(source) for source in sources):
        return None
    if not state["attributes"].keys() <= state["attribute_sources"].keys():
        return None
    if not all(isinstance(metadata.get(key), str) for key in ("name", "type")):
        return None
    if not {"_tags", "_sheet_layout", "_summary_data"} <= metadata.keys():
        return None
    tags = metadata["_tags"]
    if tags is not None and (
        not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags)
    ):
        return None
    if not all(isinstance(key, str) for key in state["attributes"]):
        return None
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return deepcopy(cast(TemporalEntityCheckpoint, value))


def _valid_source(value: object) -> bool:
    """Check the ownership fields required to construct the next edit."""
    return isinstance(value, dict) and (
        value.get("kind") == "baseline"
        or (
            value.get("kind") == "relation"
            and isinstance(value.get("relation_id"), str)
            and bool(value["relation_id"])
        )
    )
