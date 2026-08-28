"""Pure projection rules for relation edges displayed by GraphView."""

from collections import defaultdict
from copy import deepcopy
from typing import Any


class GraphProjection:
    """Project canonical relation edges into presentation-ready graph edges."""

    @staticmethod
    def project_edges(
        edges: list[dict[str, Any]],
        *,
        suppress_redundant_mentions: bool = True,
    ) -> list[dict[str, Any]]:
        """Return copied edges with GraphView-only suppression and annotations.

        Args:
            edges: Canonical edge snapshots already selected by GraphView filters.
            suppress_redundant_mentions: Hide generated WikiLink mentions when a
                different relation connects the same unordered node pair.

        Returns:
            A new list of copied edge dictionaries annotated with parallel-edge
            positions. The input list and its dictionaries are not modified.
        """
        projected = [deepcopy(edge) for edge in edges]
        if suppress_redundant_mentions:
            projected = GraphProjection._suppress_redundant_mentions(projected)
        GraphProjection._annotate_parallel_edges(projected)
        return projected

    @staticmethod
    def _pair_key(edge: dict[str, Any]) -> tuple[str, str]:
        source_id = str(edge["source_id"])
        target_id = str(edge["target_id"])
        if source_id <= target_id:
            return source_id, target_id
        return target_id, source_id

    @staticmethod
    def _is_generated_wikilink_mention(edge: dict[str, Any]) -> bool:
        attributes = edge.get("attributes")
        return (
            edge.get("rel_type") == "mentions"
            and isinstance(attributes, dict)
            and attributes.get("is_auto_generated") is True
            and attributes.get("generator") == "wikilink"
        )

    @staticmethod
    def _suppress_redundant_mentions(
        edges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        pairs_with_semantic_edges = {
            GraphProjection._pair_key(edge)
            for edge in edges
            if not GraphProjection._is_generated_wikilink_mention(edge)
        }
        return [
            edge
            for edge in edges
            if not (
                GraphProjection._is_generated_wikilink_mention(edge)
                and GraphProjection._pair_key(edge) in pairs_with_semantic_edges
            )
        ]

    @staticmethod
    def _edge_sort_key(edge: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(edge.get("rel_type", "")).casefold(),
            str(edge.get("source_id", "")),
            str(edge.get("target_id", "")),
            str(edge.get("id", "")),
        )

    @staticmethod
    def _annotate_parallel_edges(edges: list[dict[str, Any]]) -> None:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            grouped[GraphProjection._pair_key(edge)].append(edge)

        for parallel_edges in grouped.values():
            ordered = sorted(parallel_edges, key=GraphProjection._edge_sort_key)
            count = len(ordered)
            midpoint = (count - 1) / 2
            for position, edge in enumerate(ordered):
                edge["parallel_index"] = position - midpoint
                edge["parallel_count"] = count
