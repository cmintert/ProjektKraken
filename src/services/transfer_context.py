"""Calendar exchange context and reviewed, meaning-preserving ID mappings."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from src.core.calendar import CalendarConfig
from src.core.temporal_references import event_reference_ids

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService


def calendar_ids(value: Any) -> set[str]:
    """Collect calendar references inside a supported native metadata subtree."""
    if isinstance(value, list):
        return set().union(*(calendar_ids(item) for item in value))
    if not isinstance(value, dict):
        return set()
    result = {str(value["calendar_id"])} if value.get("calendar_id") else set()
    for item in value.values():
        result.update(calendar_ids(item))
    return result


def native_calendar_ids(attributes: dict[str, Any]) -> set[str]:
    """Opaque future schemas are preserved, never interpreted or remapped."""
    result: set[str] = set()
    for key in ("_temporal_v2", "temporal"):
        metadata = attributes.get(key)
        if isinstance(metadata, dict) and metadata.get("schema", 1) in {1, 2}:
            result.update(calendar_ids(metadata))
    return result


def native_event_ids(attributes: dict[str, Any]) -> set[str]:
    """Traverse supported native timing, leaving similarly named user fields alone."""
    return set().union(
        *(
            event_reference_ids(value)
            for key in ("temporal", "_temporal_v2")
            if isinstance(value := attributes.get(key), dict)
            and value.get("schema", 1) in {1, 2}
        )
    )


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        row
        for kind in ("entities", "events", "relations")
        for row in payload.get(kind, [])
    ]
    return records + [
        relation for row in records for relation in row.get("relations", [])
    ]


def calendar_signature(raw: dict[str, Any]) -> dict[str, Any]:
    """Compare all calendar semantics, including epoch and year variants."""
    config = CalendarConfig.from_dict(raw)
    errors = config.validate()
    if errors:
        raise ValueError("Invalid calendar definition: " + "; ".join(errors))
    return {
        key: value
        for key, value in {**config.to_dict(), **raw}.items()
        if key not in {"id", "name", "is_active", "created_at", "modified_at"}
    }


def export_context(
    db: DatabaseService, data: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Carry just the definitions referenced by the exported records."""
    used: set[str] = set()
    for kind in ("entities", "events", "relations"):
        for row in data.get(kind, []):
            used.update(native_calendar_ids(row.get("attributes", {})))
    configs = {
        item.id: item.to_dict()
        for item in getattr(db, "get_all_calendar_configs", lambda: [])()
    }
    return (
        {"calendars": [configs[key] for key in sorted(used) if key in configs]},
        [
            f"Calendar {key} is referenced but its definition is missing."
            for key in sorted(used - configs.keys())
        ],
    )


def _remap(value: Any, mapping: dict[str, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _remap(item, mapping)
    elif isinstance(value, dict):
        if value.get("calendar_id") in mapping:
            value["calendar_id"] = mapping[value["calendar_id"]]
        for item in value.values():
            _remap(item, mapping)


def prepare_calendars(
    db: DatabaseService,
    payload: dict[str, Any],
    context: dict[str, Any],
    options: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Require explicit compatible mappings or accepted unresolved preservation."""
    raw = context.get("calendars", [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        return ["context.calendars must be a list of calendar objects."], [], []
    definitions = {item["id"]: item for item in raw}
    if len(definitions) != len(raw):
        return ["Calendar context contains duplicate identities."], [], []
    active = db.get_active_calendar_config()
    targets = {item.id: item.to_dict() for item in db.get_all_calendar_configs()}
    used: set[str] = set()
    for row in _records(payload):
        used.update(native_calendar_ids(row.get("attributes", {})))
    errors: list[str] = []
    warnings: list[str] = []
    decisions: list[dict[str, Any]] = []
    mappings = options.get("calendar_mappings", {})
    accepted: dict[str, str] = {}
    for identity in sorted(used):
        source = definitions.get(identity)
        target_id = mappings.get(identity, identity)
        target = targets.get(target_id)
        same = target_id == identity and target is not None
        equivalent = bool(
            source
            and target
            and calendar_signature(source) == calendar_signature(target)
        )
        if target and active and target_id == active.id and (equivalent or same):
            if same and source and not equivalent:
                errors.append(f"Calendar {identity} has conflicting definitions.")
            else:
                accepted[identity] = target_id
            continue
        candidates = [
            key
            for key, value in targets.items()
            if source
            and calendar_signature(source) == calendar_signature(value)
            and active
            and key == active.id
        ]
        message = (
            f"Calendar {identity} is unresolved. Select an equivalent active "
            "calendar, exclude its records, or accept unresolved preservation."
        )
        decisions.append(
            {"source_id": identity, "candidates": candidates, "message": message}
        )
        if identity in options.get("unresolved_calendars", []):
            warnings.append(message + " Accepted unresolved; no date is invented.")
        else:
            errors.append(message)
    for row in _records(payload):
        attributes = deepcopy(row.get("attributes", {}))
        for key in ("_temporal_v2", "temporal"):
            value = attributes.get(key)
            if isinstance(value, dict) and value.get("schema", 1) in {1, 2}:
                _remap(value, accepted)
        row["attributes"] = attributes
    return errors, warnings, decisions
