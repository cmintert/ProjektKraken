"""Resolve imported identities before mutation, independently of presentation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.entities import Entity
from src.core.events import Event
from src.services.import_normalization import normalize_name

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService
    from src.services.import_service import ImportResult


def resolve_record(
    db: DatabaseService,
    kind: str,
    row: dict[str, Any],
    result: ImportResult,
    options: dict[str, Any],
) -> tuple[Entity | Event | None, str]:
    """Prefer a selected identity and UUID; require review for name collisions."""
    records = db.get_all_entities() if kind == "entity" else db.get_all_events()
    selected = row.get("_transfer_match")
    identity = selected or row.get("id")
    existing = next((item for item in records if item.id == identity), None)
    if selected and existing is None:
        raise ValueError("The selected match no longer exists.")
    if existing is not None:
        return existing, "selected_match" if selected else "uuid_match"
    external = row.get("external_id")
    if external and kind == "entity":
        existing = db._entity_repo.find_by_external_id(
            options.get("source_name", "import"), str(external)
        )
        if existing is not None:
            return existing, "external_id_match"
    candidates = [
        item
        for item in records
        if normalize_name(item.name) == normalize_name(str(row["name"]))
    ]
    if not candidates or row.get("_transfer_create"):
        return None, "new"
    if len(candidates) == 1 and not identity and not options.get("review_names"):
        return candidates[0], "name_match"
    result.ambiguous_items.append(
        {
            "type": kind,
            "name": row["name"],
            "candidates": [{"id": item.id, "name": item.name} for item in candidates],
            "reason": "Select an existing match or explicitly create a separate record.",
        }
    )
    return None, "ambiguous"


def resolve_relation(
    db: DatabaseService, row: dict[str, Any], source: str, target: str
) -> dict[str, Any] | None:
    """A UUID identifies a fact; an ID-less exact duplicate identifies itself."""
    if row.get("id"):
        existing = db._relation_repo.get_by_id(str(row["id"]))
        if row.get("_transfer_match") and existing is None:
            raise ValueError("The selected relationship no longer exists.")
        return existing
    candidates = [
        item
        for item in db.get_all_relations()
        if item["source_id"] == source
        and item["target_id"] == target
        and item["rel_type"] == row.get("rel_type", "related")
    ]
    exact = [
        item
        for item in candidates
        if item.get("attributes", {}) == row.get("attributes", {})
    ]
    if exact:
        return exact[0]
    if candidates:
        raise ValueError(
            "An ID-less relationship differs from an existing fact. "
            "Supply a new UUID or select an explicit match."
        )
    return None
