"""Detached, parent-authoritative map hierarchy without persistence or Qt."""

from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from typing import Iterable

from src.core.map import Map
from src.core.map_constants import MAP_NESTING_DEPTH_CAP

HIERARCHY_KEYS = ("map_role", "parent_map_id", "registration")


def hierarchy_attributes(attributes: dict | None) -> dict:
    """Copy only present hierarchy keys, retaining explicit legacy null values."""
    return deepcopy(
        {
            key: value
            for key, value in (attributes or {}).items()
            if key in HIERARCHY_KEYS
        }
    )


def restore_hierarchy_attributes(current: dict | None, snapshot: dict | None) -> dict:
    """Replace hierarchy keys without changing unrelated authored attributes."""
    result = deepcopy(current or {})
    for key in HIERARCHY_KEYS:
        result.pop(key, None)
    result.update(hierarchy_attributes(snapshot))
    return result


class HierarchyError(ValueError):
    """A relationship cannot be resolved or would violate tree invariants."""


class MapHierarchy:
    """Own an independent snapshot; never mutate the caller's map records."""

    def __init__(self, maps: Iterable[Map]) -> None:
        """Index copied records in their supplied deterministic order."""
        self._maps: dict[str, Map] = {}
        self._children: dict[str, list[str]] = defaultdict(list)
        for record in maps:
            if record.id in self._maps:
                raise HierarchyError(f"Duplicate map ID: {record.id}")
            self._maps[record.id] = replace(
                deepcopy(record), attributes=deepcopy(record.attributes or {})
            )
        for record in self._maps.values():
            parent = record.attributes.get("parent_map_id")
            if not isinstance(parent, str) or not parent:
                continue
            if parent is not None:
                self._children[parent].append(record.id)

    def parent_id(self, map_id: str) -> str | None:
        """Return a normalized parent reference, rejecting invalid types."""
        record = self._require(map_id)
        parent = record.attributes.get("parent_map_id")
        if parent is None or parent == "":
            return None
        if not isinstance(parent, str):
            raise HierarchyError(f"Invalid parent reference on map: {map_id}")
        return parent

    def _require(self, map_id: str) -> Map:
        record = self._maps.get(map_id)
        if record is None:
            raise HierarchyError(f"Map not found: {map_id}")
        return record

    def roots(self) -> list[Map]:
        """Return independent copies of maps without a parent reference."""
        return [
            deepcopy(m)
            for m in self._maps.values()
            if m.attributes.get("parent_map_id") in (None, "")
        ]

    def children(self, map_id: str) -> list[Map]:
        """Return children regardless of legacy role metadata."""
        return [deepcopy(self._maps[k]) for k in self._children.get(map_id, [])]

    def ancestors(self, map_id: str) -> list[Map]:
        """Resolve nearest parent first; reject cycles and dangling references."""
        visited = {map_id}
        result = []
        parent = self.parent_id(map_id)
        while parent is not None:
            if parent in visited:
                raise HierarchyError(f"Map ancestry contains a cycle: {parent}")
            visited.add(parent)
            result.append(deepcopy(self._require(parent)))
            parent = self.parent_id(parent)
        return result

    def descendants(self, map_id: str) -> list[Map]:
        """Return each reachable child once, excluding the source even in cycles."""
        self._require(map_id)
        seen = {map_id}
        pending = list(reversed(self._children.get(map_id, [])))
        result = []
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            result.append(deepcopy(self._maps[current]))
            pending.extend(reversed(self._children.get(current, [])))
        return result

    def subtree_height(self, map_id: str) -> int:
        """Measure inclusive height, rejecting cycles within the subtree."""
        self._require(map_id)
        pending = [(map_id, 1)]
        seen: set[str] = set()
        height = 1
        while pending:
            current, depth = pending.pop()
            if current in seen:
                raise HierarchyError(f"Map subtree contains a cycle: {current}")
            seen.add(current)
            height = max(height, depth)
            pending.extend((k, depth + 1) for k in self._children.get(current, []))
        return height

    def validate_change_parent(self, map_id: str, parent_id: str | None) -> None:
        """Validate the resulting affected tree, allowing a broken edge repair."""
        source = self._require(map_id)
        attrs = deepcopy(source.attributes)
        attrs.pop("parent_map_id", None)
        if parent_id is not None:
            self._require(parent_id)
            attrs["parent_map_id"] = parent_id
        proposed = MapHierarchy(
            replace(m, attributes=attrs) if m.id == map_id else m
            for m in self._maps.values()
        )
        depth = len(proposed.ancestors(map_id))
        height = proposed.subtree_height(map_id)
        if depth + height > MAP_NESTING_DEPTH_CAP:
            raise HierarchyError(
                f"Nesting depth would exceed cap of {MAP_NESTING_DEPTH_CAP} levels."
            )

    def diagnostics(self) -> dict[str, tuple[str, ...]]:
        """Report structural and legacy-role problems without repairing records."""
        result = {}
        for record in self._maps.values():
            problems = []
            try:
                parent = self.parent_id(record.id)
                self.ancestors(record.id)
                if parent and record.attributes.get("map_role") != "detail":
                    problems.append("Parent reference disagrees with legacy map role.")
                if not parent and record.attributes.get("map_role") == "detail":
                    problems.append("Detail role has no parent reference.")
            except HierarchyError as exc:
                problems.append(str(exc))
            if problems:
                result[record.id] = tuple(problems)
        return result
