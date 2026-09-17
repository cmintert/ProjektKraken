"""Small, stable updates to editor completion snapshots."""

from bisect import bisect_right

from src.core.command import LoreMutationEffect

Suggestion = tuple[str, str, str]


def apply_suggestion_effects(
    items: list[Suggestion], effects: list[LoreMutationEffect]
) -> list[Suggestion]:
    """Patch IDs while retaining name order and entity-before-event ties."""
    result = list(items)
    for effect in effects:
        result = [item for item in result if item[0] != effect["object_id"]]
        if effect["operation"] == "delete":
            continue
        snapshot = effect["snapshot"]
        assert snapshot is not None
        item = (effect["object_id"], str(snapshot["name"]), effect["object_type"])
        key = (item[1].lower(), 0 if item[2] == "entity" else 1)
        keys = [
            (name.lower(), 0 if kind == "entity" else 1)
            for _, name, kind in result
        ]
        result.insert(bisect_right(keys, key), item)
    return result
