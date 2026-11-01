"""Deterministic selection expansion for semantic edges and timing dependencies."""

from __future__ import annotations

from typing import Any

from src.services.transfer_context import native_event_ids


def select_lore(
    data: dict[str, Any],
    selected: set[str],
    include_endpoints: bool,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Expand semantic edges once, then traverse required timing to a fixed point."""
    original = set(selected)
    selected = set(selected)
    records = {row["id"]: row for kind in ("entities", "events") for row in data[kind]}
    if include_endpoints:
        for row in data["relations"]:
            endpoints = {row["source_id"], row["target_id"]}
            if endpoints & original:
                selected.update(endpoints)
    warnings: list[str] = []
    visited: set[str] = set()
    while selected - visited:
        pending = sorted(selected - visited)
        visited.update(pending)
        consumers = [records[key] for key in pending if key in records]
        consumers.extend(
            row
            for row in data["relations"]
            if {row["source_id"], row["target_id"]} <= selected
        )
        for row in consumers:
            references = native_event_ids(row.get("attributes", {}))
            selected.update(references & records.keys())
            warnings.extend(
                f"Missing timing dependency {key} required by {row['id']}."
                for key in sorted(references - records.keys())
            )
    result = {
        kind: sorted(
            [row for row in data[kind] if row["id"] in selected],
            key=lambda row: row["id"],
        )
        for kind in ("entities", "events")
    }
    result["relations"] = sorted(
        [
            row
            for row in data["relations"]
            if {row["source_id"], row["target_id"]} <= selected
        ],
        key=lambda row: row["id"],
    )
    omitted = sum(
        bool({row["source_id"], row["target_id"]} & selected)
        and not {row["source_id"], row["target_id"]} <= selected
        for row in data["relations"]
    )
    if omitted:
        warnings.append(
            f"{omitted} relationships excluded: endpoint outside selection."
        )
    return result, sorted(set(warnings)), sorted(selected - original)
