"""Tests for GraphView's pure relation-edge projection."""

from typing import Any

from src.gui.widgets.graph_view.graph_projection import GraphProjection


def _edge(
    edge_id: str,
    rel_type: str,
    source_id: str = "A",
    target_id: str = "B",
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "rel_type": rel_type,
        "attributes": attributes or {},
    }


def _generated_mention(edge_id: str = "mention") -> dict[str, Any]:
    return _edge(
        edge_id,
        "mentions",
        attributes={"is_auto_generated": True, "generator": "wikilink"},
    )


def test_single_relation_is_retained_and_annotated() -> None:
    projected = GraphProjection.project_edges([_edge("commands", "commands")])

    assert len(projected) == 1
    assert projected[0]["parallel_count"] == 1
    assert projected[0]["parallel_index"] == 0


def test_two_semantic_relations_get_distinct_parallel_positions() -> None:
    projected = GraphProjection.project_edges(
        [_edge("founded", "founded"), _edge("commands", "commands")]
    )

    assert {edge["id"] for edge in projected} == {"commands", "founded"}
    assert {edge["parallel_count"] for edge in projected} == {2}
    assert {edge["parallel_index"] for edge in projected} == {-0.5, 0.5}


def test_opposite_directions_share_parallel_group() -> None:
    projected = GraphProjection.project_edges(
        [
            _edge("commands", "commands"),
            _edge("enemy", "enemy_of", source_id="B", target_id="A"),
        ]
    )

    assert {edge["parallel_count"] for edge in projected} == {2}
    assert len({edge["parallel_index"] for edge in projected}) == 2


def test_generated_mention_is_retained_when_it_is_the_only_relation() -> None:
    projected = GraphProjection.project_edges([_generated_mention()])

    assert [edge["id"] for edge in projected] == ["mention"]


def test_generated_mention_is_suppressed_by_semantic_relation() -> None:
    projected = GraphProjection.project_edges(
        [_generated_mention(), _edge("commands", "commands")]
    )

    assert [edge["id"] for edge in projected] == ["commands"]


def test_generated_mention_is_suppressed_by_reverse_semantic_relation() -> None:
    projected = GraphProjection.project_edges(
        [
            _generated_mention(),
            _edge("member", "member_of", source_id="B", target_id="A"),
        ]
    )

    assert [edge["id"] for edge in projected] == ["member"]


def test_manual_mentions_relation_is_not_suppressed() -> None:
    projected = GraphProjection.project_edges(
        [_edge("manual", "mentions"), _edge("commands", "commands")]
    )

    assert {edge["id"] for edge in projected} == {"manual", "commands"}


def test_suppression_can_be_disabled() -> None:
    projected = GraphProjection.project_edges(
        [_generated_mention(), _edge("commands", "commands")],
        suppress_redundant_mentions=False,
    )

    assert {edge["id"] for edge in projected} == {"mention", "commands"}


def test_three_semantic_edges_replace_mention_with_deterministic_indices() -> None:
    inputs = [
        _edge("z", "supports"),
        _generated_mention(),
        _edge("a", "commands"),
        _edge("m", "founded"),
    ]

    first = GraphProjection.project_edges(inputs)
    second = GraphProjection.project_edges(list(reversed(inputs)))
    first_indices = {edge["id"]: edge["parallel_index"] for edge in first}
    second_indices = {edge["id"]: edge["parallel_index"] for edge in second}

    assert first_indices == {"a": -1, "m": 0, "z": 1}
    assert second_indices == first_indices
    assert {edge["parallel_count"] for edge in first} == {3}


def test_projection_does_not_mutate_input_edges() -> None:
    original = _edge("commands", "commands")

    projected = GraphProjection.project_edges([original])

    assert "parallel_count" not in original
    assert projected[0] is not original
