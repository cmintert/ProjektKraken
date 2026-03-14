"""Tests for MapLayerModel._compute_vis_recursive O(n×depth) fix (M6).

These tests use a spy on visible_at_zoom to count invocations and verify that
a hidden parent's children do not trigger redundant ancestor re-walks.
"""
from unittest.mock import patch

import pytest

from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.core.map import MapLayerNode
from src.app.constants import MAP_LAYER_TYPE_GROUP, MAP_LAYER_TYPE_MARKER


def _group(name: str, visible: bool = True) -> MapLayerNode:
    n = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_GROUP)
    n.visible = visible
    return n


def _marker(name: str, visible: bool = True) -> MapLayerNode:
    n = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_MARKER)
    n.visible = visible
    return n


# ---------------------------------------------------------------------------
# Correctness tests
# ---------------------------------------------------------------------------

def test_hidden_parent_hides_all_children(qtbot):
    """Children of an invisible group must all report False."""
    root = _group("Root")
    parent = _group("Parent", visible=False)
    root.children.append(parent)
    for i in range(5):
        parent.children.append(_marker(f"child-{i}", visible=True))

    model = MapLayerModel(root=root)
    result = model.compute_visibility(zoom_level=1.0)

    for child in parent.children:
        assert result[child.id] is False, f"{child.name} should be hidden"


def test_visible_children_of_visible_parent_are_visible(qtbot):
    """Children of a visible group with no zoom restrictions should be True."""
    root = _group("Root")
    parent = _group("Parent", visible=True)
    root.children.append(parent)
    for i in range(3):
        parent.children.append(_marker(f"m-{i}", visible=True))

    model = MapLayerModel(root=root)
    result = model.compute_visibility(zoom_level=1.0)

    for child in parent.children:
        assert result[child.id] is True, f"{child.name} should be visible"


def test_nested_hidden_group_hides_grandchildren(qtbot):
    """A hidden grandparent must propagate invisibility through two levels."""
    root = _group("Root")
    grp_a = _group("A", visible=False)
    grp_b = _group("B", visible=True)
    grp_a.children.append(grp_b)
    grandchild = _marker("leaf")
    grp_b.children.append(grandchild)
    root.children.append(grp_a)

    model = MapLayerModel(root=root)
    result = model.compute_visibility(zoom_level=1.0)
    assert result[grandchild.id] is False


# ---------------------------------------------------------------------------
# Performance regression test: hidden parent tree calls visible_at_zoom
# fewer times than the old O(n×depth) behaviour.
# ---------------------------------------------------------------------------

def _build_deep_tree(depth: int, width: int) -> tuple[MapLayerNode, list[MapLayerNode]]:
    """Build a *depth*-deep tree, all children hidden via the root.

    Returns (root, leaf_nodes).
    """
    root = _group("Root")
    # Top-level group is hidden — all descendants should be skipped
    top = _group("Top", visible=False)
    root.children.append(top)
    leaves = []
    current_level = [top]
    for d in range(depth - 1):
        next_level = []
        for parent in current_level:
            for _ in range(width):
                child = _group(f"g-{d}-{len(next_level)}", visible=True)
                parent.children.append(child)
                next_level.append(child)
        current_level = next_level
    # Bottom leaves
    for parent in current_level:
        leaf = _marker(f"leaf-{len(leaves)}", visible=True)
        parent.children.append(leaf)
        leaves.append(leaf)
    return root, leaves


def test_hidden_subtree_avoids_redundant_ancestor_walks(qtbot):
    """_compute_vis_recursive must not call visible_at_zoom for children of
    a hidden parent — short-circuit on parent_visible=False.

    The old code called visible_at_zoom once per node unconditionally, which
    internally re-walked all ancestors. With the fix, children of a False
    parent skip the call entirely.

    We build a tree where the root is visible but the top-level group is
    hidden. Nodes deeper in the tree should not call visible_at_zoom at all.
    """
    root, leaves = _build_deep_tree(depth=3, width=4)
    model = MapLayerModel(root=root)
    model.invalidate_cache()

    call_count = []

    original_visible_at_zoom = model.visible_at_zoom

    def spy_visible_at_zoom(node, zoom_level):
        call_count.append(node.id)
        return original_visible_at_zoom(node, zoom_level)

    with patch.object(model, "visible_at_zoom", side_effect=spy_visible_at_zoom):
        result = model.compute_visibility(zoom_level=1.0)

    # All leaves must be False
    for leaf in leaves:
        assert result[leaf.id] is False

    # Under the old O(n×depth) code, every node (including grandchildren)
    # called visible_at_zoom. With the fix, once the hidden top-group is
    # checked, its children must NOT call visible_at_zoom again — they
    # inherit parent_visible=False and short-circuit.
    # The hidden top group itself is 1 call; all its children should be 0.
    top_group = root.children[0]
    # Only the top group node should appear in calls; none of its children
    assert all(nid == top_group.id for nid in call_count), (
        f"Expected only top-group call; got calls for: "
        f"{[nid for nid in call_count if nid != top_group.id]}"
    )
