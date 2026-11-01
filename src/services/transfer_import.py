"""Prepare accurate import previews without mutating the active database."""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any

from src.core.events import Event
from src.core.temporal_references import remap_temporal_references
from src.core.transfer import LORE_KINDS
from src.services.db_service import DatabaseService
from src.services.import_service import ImportResult, ImportService
from src.services.repositories.transfer_repository import changes, revision, snapshot
from src.services.transfer_context import prepare_calendars
from src.services.transfer_diagnostics import reference_diagnostics
from src.services.transfer_validation import validate_record


def _validate_nested(
    row: dict[str, Any],
    token: str,
    options: dict[str, Any],
    parser: ImportService,
) -> list[str]:
    """Validate nested Relations before endpoint remapping or clone writes."""
    errors: list[str] = []
    nested = row.get("relations", [])
    if not isinstance(nested, list):
        errors.append(f"{token}: Relations must be a list of objects.")
    else:
        for rel_index, relation in enumerate(nested):
            rel_token = f"{token}:relations:{rel_index}"
            if not isinstance(relation, dict):
                errors.append(f"{rel_token}: A relationship must be an object.")
                continue
            relation, _source = _prepare_row(
                relation, rel_token, {**options, "mode": row["import_action"]}
            )
            nested[rel_index] = relation
            errors.extend(
                f"{rel_token}: {message}"
                for message in validate_record("relations", relation, parser)
            )
    return errors


def _prepare_row(
    incoming: dict[str, Any],
    token: str,
    options: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Keep transfer control fields owned by review options, never by source input."""
    row = copy.deepcopy(incoming)
    source = row.pop("_transfer_source", "Input")
    for key in list(row):
        if key.startswith("_transfer_"):
            row.pop(key)
    row["import_action"] = options.get("actions", {}).get(
        token, options.get("mode", "skip")
    )
    row["_transfer_token"] = token
    if options.get("matches", {}).get(token):
        if row.get("id"):
            row.setdefault("_transfer_original_id", row["id"])
        row["id"] = options["matches"][token]
        row["_transfer_match"] = row["id"]
    if options.get("actions", {}).get(token) == "create":
        if row.get("id"):
            row["_transfer_original_id"] = row["id"]
        row["id"] = options["proposed_ids"].setdefault(token, str(uuid.uuid4()))
        row["_transfer_create"] = True
        row.pop("_transfer_match", None)
    if not row.get("id"):
        allocated = options["proposed_ids"].setdefault(token, str(uuid.uuid4()))
        if token.startswith("relations:") or ":relations:" in token:
            row["_transfer_allocated_id"] = allocated
        else:
            row["id"] = allocated
    return row, str(source)


def _prepare_payload(
    data: dict[str, Any], options: dict[str, Any], parser: ImportService
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    payload: dict[str, Any] = {}
    errors: list[str] = []
    sources: dict[str, str] = {}
    for kind in LORE_KINDS:
        records: list[dict[str, Any]] = []
        if not isinstance(data.get(kind, []), list):
            errors.append(f"{kind} must be a list of objects.")
            payload[kind] = records
            continue
        for index, incoming in enumerate(data.get(kind, [])):
            token = f"{kind}:{index}"
            if token in options.get("excluded", []):
                continue
            if not isinstance(incoming, dict):
                errors.append(f"{token}: A record must be a JSON object.")
                continue
            row, source = _prepare_row(incoming, token, options)
            sources[token] = source
            errors.extend(
                f"{token} ({sources[token]}): {error}"
                for error in validate_record(kind, row, parser)
            )
            errors.extend(_validate_nested(row, token, options, parser))
            records.append(row)
        payload[kind] = records
    errors.extend(_duplicate_ids(payload))
    return payload, errors, sources


def _duplicate_ids(payload: dict[str, Any]) -> list[str]:
    """Reject contradictory repeated identities, including nested Relations."""
    seen: set[str] = set()
    errors: list[str] = []
    records = [row for kind in LORE_KINDS for row in payload[kind]]
    records.extend(
        relation
        for row in list(records)
        if isinstance(row.get("relations"), list)
        for relation in row.get("relations", [])
        if isinstance(relation, dict)
    )
    for row in records:
        identity = row.get("id") or row.get("_transfer_allocated_id")
        if identity in seen:
            errors.append(
                f"Duplicate ID {identity} in the input. Exclude or correct a record."
            )
        if identity:
            seen.add(identity)
    return errors


def _import_records(
    parser: ImportService,
    payload: dict[str, Any],
    options: dict[str, Any],
    db: DatabaseService,
) -> ImportResult:
    # Resolve identities first, then remap all cross-file endpoint references.
    relations = payload.pop("relations", [])
    original_ids: dict[int, str] = {}
    nested: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for kind in ("entities", "events"):
        for row in payload[kind]:
            if row.get("id"):
                original_ids[id(row)] = row.pop("_transfer_original_id", row["id"])
            nested.append((row, row.pop("relations", [])))
    result = parser._materialize_batch(
        payload, {**options, "dry_run": False, "review_names": True}
    )
    remap = {
        original_ids[id(row)]: row["id"]
        for row, _ in nested
        if id(row) in original_ids and row.get("id")
    }
    for row, row_relations in nested:
        _remap_imported_record(db, row, remap, result.actions)
        for relation in row_relations:
            relation["source_id"] = row.get("id")
            relation.setdefault("import_action", row["import_action"])
            relations.append(relation)
    for relation in relations:
        relation["attributes"] = remap_temporal_references(
            relation.get("attributes", {}), remap
        )
        for endpoint in ("source_id", "target_id"):
            if relation.get(endpoint) in remap:
                relation[endpoint] = remap[relation[endpoint]]
    linked = parser._materialize_batch(
        {"relations": relations}, {**options, "dry_run": False, "review_names": True}
    )
    result.created_relations.extend(linked.created_relations)
    result.errors.extend(linked.errors)
    result.warnings.extend(linked.warnings)
    result.actions.extend(linked.actions)
    return result


def _remap_imported_record(
    db: DatabaseService,
    row: dict[str, Any],
    remap: dict[str, str],
    actions: list[dict[str, Any]],
) -> None:
    """Change only metadata supplied by an accepted incoming record."""
    action = next((item for item in actions if item.get("id") == row.get("id")), {})
    if not action or action.get("action") == "skip":
        return
    event = action.get("type") == "event"
    record = db.get_event(row["id"]) if event else db.get_entity(row["id"])
    if record is None:
        return
    incoming = row.get("attributes", {})
    revised = remap_temporal_references(incoming, remap)
    changed = False
    for key in ("temporal", "_temporal_v2"):
        if key in incoming and incoming[key] != revised[key]:
            record.attributes[key] = revised[key]
            changed = True
    if changed:
        if isinstance(record, Event):
            db.insert_event(record)
        else:
            db.insert_entity(record)


def prepare_import(
    db: DatabaseService, data: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    """Run the importer on a private snapshot and return reviewable row deltas."""
    options = copy.deepcopy(options)
    options.setdefault("import_time", time.time())
    options.setdefault("proposed_ids", {})
    connection = db.get_connection()
    if connection is None:
        raise ValueError("No world is open.")
    clone = DatabaseService()
    clone.connect()
    target = clone.get_connection()
    assert target is not None
    try:
        connection.backup(target)
        before = snapshot(target)
        parser = ImportService(clone, options["import_time"])
        payload, errors, sources = _prepare_payload(data, options, parser)
        context = data.get("context", {})
        if not isinstance(context, dict):
            errors.append("Exchange context must be a JSON object.")
            context = {}
        context_errors: list[str] = []
        context_warnings: list[str] = []
        calendar_decisions: list[dict[str, Any]] = []
        if not errors:
            try:
                context_errors, context_warnings, calendar_decisions = (
                    prepare_calendars(clone, payload, context, options)
                )
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                context_errors.append(f"Invalid calendar context: {exc}")
        errors.extend(context_errors)
        if errors:
            return {
                "errors": errors,
                "sources": sources,
                "delta": [],
                "actions": [],
                "options": options,
                "calendar_decisions": calendar_decisions,
                "warnings": context_warnings,
            }
        result = _import_records(parser, payload, options, clone)
        after = snapshot(target)
        reference_errors, reference_warnings, dependency_decisions = (
            reference_diagnostics(clone, changes(before, after), options)
        )
        errors.extend(reference_errors)
        from src.services.event_timing.planning import snapshot_fingerprint
        from src.services.event_timing.store import capture
        from src.services.event_timing.transfer import project_import

        timing_review = project_import(db, changes(before, after), clone)
        if timing_review is not None:
            errors.extend(timing_review["errors"])
            after = snapshot(target)
        errors.extend(
            f"Ambiguous {item['type']} '{item['name']}': "
            "select a match or exclude the record."
            for item in result.ambiguous_items
        )
        errors.extend(result.errors)
        ids = {row["id"] for kind in ("entities", "events") for row in after[kind]}
        delta = changes(before, after)
        for change in delta:
            if change["table"] == "relations" and change["after"]:
                relation = change["after"]
                if relation["source_id"] not in ids or relation["target_id"] not in ids:
                    errors.append(
                        "A relationship endpoint does not exist. Correct or exclude it."
                    )
        errors.extend(
            warning
            for warning in result.warnings
            if "Unresolved" in warning or warning.startswith("Failed")
        )
        return {
            "errors": errors,
            "warnings": list(data.get("warnings", []))
            + context_warnings
            + reference_warnings
            + result.warnings,
            "dependency_decisions": dependency_decisions,
            "calendar_decisions": calendar_decisions,
            "sources": sources,
            "ambiguous": result.ambiguous_items,
            "actions": result.actions,
            "delta": delta,
            "revision": revision(before),
            "context_revision": snapshot_fingerprint(capture(db)),
            "db_path": db.db_path,
            "source_hashes": data.get("source_hashes", {}),
            "timing_review": timing_review,
            "options": options,
            "original_data": copy.deepcopy(data),
        }
    finally:
        clone.close()
