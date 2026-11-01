"""Record-level dependency and opaque-version diagnostics for reviewed transfers."""

from __future__ import annotations

import json
from typing import Any

from src.services.db_service import DatabaseService
from src.services.transfer_context import native_event_ids


def reference_diagnostics(
    db: DatabaseService,
    delta: list[dict[str, Any]],
    options: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Missing Event dependencies need explicit unresolved acceptance."""
    present = {event.id for event in db.get_all_events()}
    missing: dict[str, set[str]] = {}
    warnings: list[str] = []
    for change in delta:
        row = change["after"]
        if row is None or change["table"] not in {"entities", "events", "relations"}:
            continue
        attributes = row.get("attributes", {})
        if isinstance(attributes, str):
            attributes = json.loads(attributes)
        for key in ("_temporal_v2", "temporal"):
            value = attributes.get(key)
            if isinstance(value, dict) and value.get("schema", 1) not in {1, 2}:
                warnings.append(
                    f"{row['id']}: {key} version {value['schema']} is "
                    "preserved opaquely; it is not interpreted or remapped."
                )
        for identity in native_event_ids(attributes) - present:
            missing.setdefault(identity, set()).add(row["id"])
    errors: list[str] = []
    decisions: list[dict[str, Any]] = []
    for identity, owners in sorted(missing.items()):
        message = (
            f"Missing Event dependency {identity}, used by {', '.join(sorted(owners))}."
        )
        decisions.append({"source_id": identity, "message": message})
        if identity in options.get("unresolved_events", []):
            warnings.append(message + " Accepted unresolved; no date is invented.")
        else:
            errors.append(
                message
                + " Include its source, exclude its users, or accept unresolved."
            )
    return errors, warnings, decisions
