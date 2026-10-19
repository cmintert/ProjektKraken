"""Detached patch planning for source-aware temporal entity mutations.

The command owns fresh reads, conflict checks, payload validation, persistence,
transactions and history. Planning neither reads storage nor allocates records.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class TemporalEditPlanError(ValueError):
    """An expected planning rejection with the existing user-facing message."""


@dataclass(frozen=True)
class TemporalEntityEditPlan:
    """Owned baseline, relation snapshots and insertion-ordered dated payloads."""

    baseline: dict[str, Any]
    baseline_changed: bool
    sync_tags: bool
    before_relations: dict[str, dict[str, Any]]
    relation_updates: dict[str, dict[str, Any]]
    dated_updates: dict[tuple[str, str], dict[str, Any]]


class TemporalEntityEditPlanner:
    """Prepare edits from snapshots without changing any supplied nested value."""

    @staticmethod
    def source_relation_ids(
        expected_state: dict[str, Any], patches: list[dict[str, Any]]
    ) -> tuple[str, ...]:
        """List distinct source owners for command-owned snapshot collection."""
        ids: dict[str, None] = {}
        for patch in patches:
            if patch.get("scope", "source") != "source":
                continue
            owner = _source_owner(expected_state, patch)
            if owner is not None and owner["kind"] != "baseline":
                ids[owner["relation_id"]] = None
        return tuple(ids)

    @staticmethod
    def prepare(
        entity_snapshot: dict[str, Any],
        expected_state: dict[str, Any],
        patches: list[dict[str, Any]],
        metadata: dict[str, Any],
        relation_snapshots: dict[str, dict[str, Any] | None],
    ) -> TemporalEntityEditPlan:
        """Route patches, retaining first-use order and exact payload semantics."""
        baseline = deepcopy(entity_snapshot)
        _apply_metadata(baseline, metadata)
        before: dict[str, dict[str, Any]] = {}
        relations: dict[str, dict[str, Any]] = {}
        dated: dict[tuple[str, str], dict[str, Any]] = {}
        for patch in deepcopy(patches):
            scope, relation_id = _destination(expected_state, patch)
            if scope == "baseline":
                _apply_baseline_patch(baseline, patch)
            elif scope == "relation":
                assert relation_id is not None
                if relation_id not in relations:
                    relation = relation_snapshots.get(relation_id)
                    if relation is None or relation["target_id"] != baseline["id"]:
                        raise TemporalEditPlanError(
                            "The source relation no longer exists"
                        )
                    before[relation_id] = deepcopy(relation)
                    relations[relation_id] = deepcopy(relation)
                payload = relations[relation_id]["attributes"].setdefault("payload", {})
                _apply_payload_patch(payload, patch)
            else:
                _apply_dated_patch(dated, patch)
        changed = any(
            baseline[key] != entity_snapshot[key]
            for key in ("name", "type", "description", "attributes")
        )
        return TemporalEntityEditPlan(
            baseline,
            changed,
            changed and "_tags" in metadata.get("hidden_attributes", {}),
            before,
            relations,
            dated,
        )


def _source_owner(
    expected: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any] | None:
    """Read the viewed field owner without resolving any database state."""
    return (
        expected["description_source"]
        if patch["field"] == "description"
        else expected["attribute_sources"].get(patch.get("key"))
    )


def _destination(
    expected: dict[str, Any], patch: dict[str, Any]
) -> tuple[str, str | None]:
    """Resolve source edits; relation is an internal destination, not a scope."""
    scope = patch.get("scope", "source")
    if scope == "source":
        owner = _source_owner(expected, patch)
        if owner is None:
            raise TemporalEditPlanError("A new field needs a baseline or dated scope")
        if owner["kind"] == "baseline":
            return "baseline", None
        return "relation", owner["relation_id"]
    if scope not in {"baseline", "dated"}:
        raise TemporalEditPlanError(f"Unknown edit scope: {scope}")
    return scope, None


def _apply_metadata(baseline: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Prepare baseline-only metadata without aliasing the caller's values."""
    for key, value in deepcopy(metadata.get("hidden_attributes", {})).items():
        if key not in {"_tags", "_sheet_layout", "_summary_data"}:
            raise TemporalEditPlanError(f"Unsupported baseline metadata: {key}")
        if value is None:
            baseline["attributes"].pop(key, None)
        else:
            baseline["attributes"][key] = value
    for key in ("name", "type"):
        if key in metadata:
            baseline[key] = deepcopy(metadata[key])


def _apply_baseline_patch(baseline: dict[str, Any], patch: dict[str, Any]) -> None:
    """Apply the original baseline description/attribute mutation rules."""
    if patch["field"] == "description":
        baseline["description"] = patch["value"]
    else:
        key = patch.get("key")
        assert isinstance(key, str)
        if patch["action"] in {"unset", "remove_override"}:
            baseline["attributes"].pop(key, None)
        else:
            baseline["attributes"][key] = patch["value"]


def _apply_dated_patch(
    dated: dict[tuple[str, str], dict[str, Any]], patch: dict[str, Any]
) -> None:
    """Group by the original untrimmed identity; creation trims the event name."""
    event_id = patch.get("event_id", "")
    event_name = patch.get("event_name", "")
    if not event_id and not event_name.strip():
        raise TemporalEditPlanError("Choose an event or enter a new event name")
    payload = dated.setdefault(
        (event_id, event_name), {"attributes": {}, "unset_attributes": []}
    )
    _apply_payload_patch(payload, patch)


def _apply_payload_patch(payload: dict[str, Any], patch: dict[str, Any]) -> None:
    """Change only the requested field, preserving masking/override semantics."""
    if patch["field"] == "description":
        if patch["action"] == "remove_override":
            payload.pop("description", None)
        else:
            payload["description"] = patch["value"]
        return
    key = patch["key"]
    attrs = payload.setdefault("attributes", {})
    unsets = payload.setdefault("unset_attributes", [])
    if patch["action"] == "set":
        attrs[key] = patch["value"]
        if key in unsets:
            unsets.remove(key)
    else:
        attrs.pop(key, None)
        if patch["action"] == "unset" and key not in unsets:
            unsets.append(key)
