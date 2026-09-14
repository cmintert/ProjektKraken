"""Prepare accurate import previews without mutating the active database."""

from __future__ import annotations

import copy
import math
from typing import Any

from src.core.transfer import LORE_KINDS
from src.services.db_service import DatabaseService
from src.services.import_service import ImportResult, ImportService
from src.services.repositories.transfer_repository import changes, revision, snapshot


def _validate_record(
    kind: str, row: dict[str, Any], parser: ImportService
) -> list[str]:
    errors: list[str] = []
    if kind != "relations" and not str(row.get("name", "")).strip():
        errors.append("A name is required.")
    if not isinstance(row.get("attributes", {}), dict):
        errors.append("Attributes must be a JSON object.")
    if "tags" in row and (
        not isinstance(row["tags"], list)
        or any(not isinstance(tag, str) for tag in row["tags"])
    ):
        errors.append("Tags must be a JSON list of names.")
    if kind != "events":
        return errors
    raw_date = row.get("lore_date")
    if raw_date is None or str(raw_date).strip() == "":
        return errors + ["An event date is required."]
    try:
        raw_date = float(raw_date)
    except (ValueError, TypeError):
        pass
    value, duration, explicit = parser._parse_lore_date(raw_date)
    if not explicit or not math.isfinite(value):
        errors.append(f"Invalid date {raw_date!r}.")
    else:
        row["lore_date"] = value
        row.setdefault("lore_duration", duration)
    try:
        if not math.isfinite(float(row.get("lore_duration", 0))):
            raise ValueError("non-finite duration")
    except (ValueError, TypeError):
        errors.append("Duration must be a finite number of days.")
    return errors


def _prepare_payload(
    data: dict[str, Any], options: dict[str, Any], parser: ImportService
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    payload: dict[str, Any] = {}
    errors: list[str] = []
    sources: dict[str, str] = {}
    item_ids: set[str] = set()
    for kind in LORE_KINDS:
        records = []
        for index, incoming in enumerate(data.get(kind, [])):
            token = f"{kind}:{index}"
            if token in options.get("excluded", []):
                continue
            row = copy.deepcopy(incoming)
            sources[token] = row.pop("_transfer_source", "Input")
            row["import_action"] = options.get("actions", {}).get(
                token, options.get("mode", "skip")
            )
            if options.get("matches", {}).get(token):
                row["id"] = options["matches"][token]
            item_id = str(row.get("id", ""))
            if kind != "relations" and item_id and item_id in item_ids:
                errors.append(
                    f"{token}: Duplicate ID in the input. "
                    "Exclude or correct one record."
                )
            if kind != "relations" and item_id:
                item_ids.add(item_id)
            errors.extend(
                f"{token} ({sources[token]}): {error}"
                for error in _validate_record(kind, row, parser)
            )
            records.append(row)
        payload[kind] = records
    return payload, errors, sources


def _import_records(
    parser: ImportService, payload: dict[str, Any], options: dict[str, Any]
) -> ImportResult:
    # Resolve identities first, then remap all cross-file endpoint references.
    relations = payload.pop("relations", [])
    original_ids: dict[int, str] = {}
    nested: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for kind in ("entities", "events"):
        for row in payload[kind]:
            if row.get("id"):
                original_ids[id(row)] = row["id"]
            nested.append((row, row.pop("relations", [])))
    result = parser.import_batch(payload, {**options, "dry_run": False})
    remap = {
        original_ids[id(row)]: row["id"]
        for row, _ in nested
        if id(row) in original_ids and row.get("id")
    }
    for row, row_relations in nested:
        for relation in row_relations:
            relation["source_id"] = row.get("id")
            relation.setdefault("import_action", row["import_action"])
            relations.append(relation)
    for relation in relations:
        for endpoint in ("source_id", "target_id"):
            if relation.get(endpoint) in remap:
                relation[endpoint] = remap[relation[endpoint]]
    linked = parser.import_batch(
        {"relations": relations}, {**options, "dry_run": False}
    )
    result.created_relations.extend(linked.created_relations)
    result.errors.extend(linked.errors)
    result.warnings.extend(linked.warnings)
    result.actions.extend(linked.actions)
    return result


def prepare_import(
    db: DatabaseService, data: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    """Run the importer on a private snapshot and return reviewable row deltas."""
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
        parser = ImportService(clone)
        payload, errors, sources = _prepare_payload(data, options, parser)
        if errors:
            return {
                "errors": errors,
                "sources": sources,
                "delta": [],
                "actions": [],
                "options": options,
            }
        result = _import_records(parser, payload, options)
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
            "warnings": list(data.get("warnings", [])) + result.warnings,
            "sources": sources,
            "ambiguous": result.ambiguous_items,
            "actions": result.actions,
            "delta": delta,
            "revision": revision(before),
            "db_path": db.db_path,
            "source_hashes": data.get("source_hashes", {}),
            "options": options,
        }
    finally:
        clone.close()
