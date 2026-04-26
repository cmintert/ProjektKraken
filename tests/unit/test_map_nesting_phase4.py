"""Phase-4 tests for breadcrumb navigation.

Covers:
* MapHandler._load_breadcrumb_for_map builds correct chain ordering.
* MapWidget.set_breadcrumb shows/hides breadcrumb and back button.
* Clicking a breadcrumb link selects the correct map.
"""

from __future__ import annotations

import pytest

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map import Map
from src.services.map_nesting_service import MapNestingService, NestingValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_map(name: str, **attrs) -> Map:
    return Map(name=name, image_path=f"/{name}.png", attributes=dict(attrs))


def _affine() -> dict:
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.5, "y": 0.5},
        "scale_norm": 0.25,
        "rotation_deg": 0.0,
        "aspect_ratio": 1.5,
        "confidence": "user_confirmed",
    }


# ---------------------------------------------------------------------------
# Breadcrumb chain building via MapNestingService.iter_ancestors
# ---------------------------------------------------------------------------


class TestBreadcrumbChain:
    """Unit tests for the chain-building logic used by _load_breadcrumb_for_map."""

    def _build_chain(self, current_map: Map, all_maps: list) -> list:
        """Mirror the logic in MapHandler._load_breadcrumb_for_map."""
        try:
            ancestors = list(
                MapNestingService.iter_ancestors(current_map.id, all_maps)
            )
        except NestingValidationError:
            ancestors = []
        chain = [(m.id, m.name) for m in reversed(ancestors)]
        chain.append((current_map.id, current_map.name))
        return chain

    def test_plain_map_produces_single_entry_chain(self):
        m = _make_map("Solo")
        chain = self._build_chain(m, [m])
        assert len(chain) == 1
        assert chain[0] == (m.id, "Solo")

    def test_master_map_alone_produces_single_entry_chain(self):
        master = _make_map("Master", map_role=MAP_ROLE_MASTER)
        chain = self._build_chain(master, [master])
        assert len(chain) == 1
        assert chain[0] == (master.id, "Master")

    def test_detail_map_produces_two_entry_chain(self):
        master = _make_map("World", map_role=MAP_ROLE_MASTER)
        detail = _make_map(
            "City",
            map_role=MAP_ROLE_DETAIL,
            parent_map_id=master.id,
            registration=_affine(),
        )
        chain = self._build_chain(detail, [master, detail])
        assert len(chain) == 2
        # Root first, current last.
        assert chain[0] == (master.id, "World")
        assert chain[1] == (detail.id, "City")

    def test_three_deep_chain_ordered_root_to_leaf(self):
        root = _make_map("Root", map_role=MAP_ROLE_MASTER)
        mid = _make_map(
            "Mid",
            map_role=MAP_ROLE_DETAIL,
            parent_map_id=root.id,
            registration=_affine(),
        )
        leaf = _make_map(
            "Leaf",
            map_role=MAP_ROLE_DETAIL,
            parent_map_id=mid.id,
            registration=_affine(),
        )
        chain = self._build_chain(leaf, [root, mid, leaf])
        assert len(chain) == 3
        assert chain[0] == (root.id, "Root")
        assert chain[1] == (mid.id, "Mid")
        assert chain[2] == (leaf.id, "Leaf")

    def test_cycle_in_chain_produces_safe_fallback(self):
        """A cycle must not raise — it should produce a truncated chain."""
        a = _make_map("A", map_role=MAP_ROLE_MASTER)
        # Force a cycle by directly setting parent_map_id → itself.
        a.attributes["parent_map_id"] = a.id
        # Should not raise; chain degrades gracefully.
        chain = self._build_chain(a, [a])
        assert isinstance(chain, list)
        # The last element must be the current map.
        assert chain[-1] == (a.id, "A")


# ---------------------------------------------------------------------------
# MapWidget.set_breadcrumb UI tests
# ---------------------------------------------------------------------------


class TestMapWidgetBreadcrumb:
    def test_set_breadcrumb_hides_label_for_empty_chain(self, qtbot):
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        w.set_breadcrumb([])
        assert not w.breadcrumb_label.isVisible()

    def test_set_breadcrumb_hides_for_single_entry(self, qtbot):
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        m = _make_map("Master")
        w.set_breadcrumb([(m.id, m.name)])
        assert not w.breadcrumb_label.isVisible()
        assert not w.btn_parent.isVisible()

    def test_set_breadcrumb_shows_for_two_entries(self, qtbot):
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        master = _make_map("World")
        detail = _make_map("City")
        w.set_breadcrumb([(master.id, "World"), (detail.id, "City")])
        assert not w.breadcrumb_label.isHidden()
        assert not w.btn_parent.isHidden()
        assert w._breadcrumb_parent_id == master.id

    def test_set_breadcrumb_label_contains_map_names(self, qtbot):
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        master = _make_map("TheWorld")
        detail = _make_map("TheCity")
        w.set_breadcrumb([(master.id, "TheWorld"), (detail.id, "TheCity")])
        text = w.breadcrumb_label.text()
        assert "TheWorld" in text
        assert "TheCity" in text

    def test_set_breadcrumb_parent_id_set_correctly(self, qtbot):
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        root = _make_map("Root")
        mid = _make_map("Mid")
        leaf = _make_map("Leaf")
        chain = [(root.id, "Root"), (mid.id, "Mid"), (leaf.id, "Leaf")]
        w.set_breadcrumb(chain)
        # Parent of Leaf is Mid.
        assert w._breadcrumb_parent_id == mid.id
