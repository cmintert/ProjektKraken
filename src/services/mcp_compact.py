"""Lossless response-local interning at explicitly factual MCP paths only."""

import copy
import json
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

Path = tuple[str | int, ...]
_MIN_OCCURRENCES = 2
# Everything else is a leaf: especially authored values and temporal evidence.
_SECTIONS = frozenset(
    {
        "rows",
        "results",
        "data",
        "participants",
        "locations",
        "mentions",
        "previous_events",
        "concurrent_events",
        "next_events",
        "direct_relations",
        "neighborhood_relations",
        "linked_references",
        "temporal_history",
        "event_appearances",
        "co_appearances",
        "shared_tags",
        "shared_maps",
        "spatial",
        "parent_maps",
        "map_appearances",
        "tags",
        "event",
        "events",
        "item",
        "source",
        "target",
        "anchor",
        "provenance",
        "effective_description",
        "possible_changes",
    }
)


def _record(value: dict[str, Any]) -> bool:
    return isinstance(value.get("id"), str) or (
        "kind" in value and any(key in value for key in ("relation_id", "event_id"))
    )


def _records(value: Any, path: Path = ()) -> Iterator[tuple[Path, dict[str, Any]]]:
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _records(item, (*path, index))
    elif isinstance(value, dict):
        if value.get("status") == "NOT_FOUND":
            return
        if _record(value):
            yield path, value
        for key, item in value.items():
            if key in _SECTIONS:
                yield from _records(item, (*path, key))
            elif key == "attributes" and isinstance(item, list):
                for index, attribute in enumerate(item):
                    if isinstance(attribute, dict) and "source" in attribute:
                        yield from _records(
                            attribute["source"], (*path, key, index, "source")
                        )


def _encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _parent(content: Any, path: Path) -> Any:
    for part in path[:-1]:
        try:
            if isinstance(content, dict):
                content = content[part]
            elif isinstance(content, list) and isinstance(part, int):
                content = content[part]
            else:
                return None
        except (KeyError, IndexError, TypeError):
            return None
    return content


def compact_data(data: dict[str, Any]) -> dict[str, Any]:
    """Pool identical factual records only when serialized bytes decrease."""
    content = copy.deepcopy(data)
    references: dict[str, Any] = {}
    groups: dict[str, list[Path]] = defaultdict(list)
    for path, record in _records(data):
        if path:
            groups[_encoded(record)].append(path)
    for encoded, paths in sorted(groups.items(), key=lambda pair: -len(pair[0])):
        live = []
        for path in paths:
            parent = _parent(content, path)
            if parent is not None:
                try:
                    if _encoded(parent[path[-1]]) == encoded:
                        live.append((parent, path[-1]))
                except (KeyError, IndexError, TypeError):
                    continue
        if len(live) < _MIN_OCCURRENCES:
            continue
        key = f"r{len(references) + 1}"
        original = live[0][0][live[0][1]]
        before = len(_encoded({"content": content, "references": references}).encode())
        references[key] = original
        for parent, part in live:
            parent[part] = {"$ref": key}
        after = len(_encoded({"content": content, "references": references}).encode())
        if after >= before:
            del references[key]
            for parent, part in live:
                parent[part] = original
    return {"content": content, "references": references}


def record_ids(data: Any) -> list[str]:
    """Collect factual IDs without interpreting authored attribute values as IDs."""
    if not isinstance(data, dict):
        return []
    roots = [data]
    if "content" in data and "references" in data:
        roots = [data["content"], *data["references"].values()]
    found: list[str] = []
    for root in roots:
        if isinstance(root, dict):
            found.extend(
                root[key]
                for key in ("entity_id", "event_id")
                if isinstance(root.get(key), str)
            )
        for _, record in _records(root):
            found.extend(
                record[key]
                for key in ("id", "event_id", "relation_id")
                if isinstance(record.get(key), str) and record[key]
            )
    return list(dict.fromkeys(found))
