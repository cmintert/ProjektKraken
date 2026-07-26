"""Phase-3 tests for footprint overlay items and MapGraphicsView integration.

Covers:
* DetailMapFootprintItem construction and registration accessors.
* set_footprints / clear_footprints on MapGraphicsView.
* FootprintItem signals: detail_map_clicked re-emitted by the view.
* Edit-mode state transitions: start, confirm, cancel.
* Keyboard nudge and rotation in edit mode.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.detail_map_footprint_item import DetailMapFootprintItem
from src.gui.widgets.map.map_graphics_view import MapGraphicsView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _affine(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 0.25,
    rotation: float = 0.0,
    aspect: float = 1.5,
) -> Dict[str, Any]:
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": cx, "y": cy},
        "scale_norm": scale,
        "rotation_deg": rotation,
        "aspect_ratio": aspect,
        "confidence": "user_confirmed",
    }


def _make_footprint_data(
    detail_id: str = "d1",
    name: str = "City",
    parent_id: str = "p1",
    reg: Dict[str, Any] | None = None,
) -> dict:
    return {
        "id": detail_id,
        "name": name,
        "parent_map_id": parent_id,
        "registration": reg or _affine(),
    }


@pytest.fixture
def view(qtbot):
    """MapGraphicsView with a 200×100 px pixmap loaded."""
    v = MapGraphicsView()
    qtbot.addWidget(v)

    img = QImage(200, 100, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(img)
    v.pixmap_item = QGraphicsPixmapItem(pixmap)
    v.scene.addItem(v.pixmap_item)
    v.coord_system.set_scene_rect(QRectF(0, 0, 200, 100))
    v.scene.setSceneRect(QRectF(0, 0, 200, 100))
    return v


# ---------------------------------------------------------------------------
# DetailMapFootprintItem unit tests
# ---------------------------------------------------------------------------


class TestDetailMapFootprintItem:
    def test_construction_stores_registration(self):
        reg = _affine()
        item = DetailMapFootprintItem(
            detail_map_id="d1",
            name="Test",
            parent_map_id="p1",
            registration=reg,
            image_w=200.0,
            image_h=100.0,
        )
        assert item.detail_map_id == "d1"
        assert item.parent_map_id == "p1"
        assert item.current_registration() == reg
        assert item.current_registration() is not reg  # defensive copy

    def test_bounding_rect_covers_full_image(self):
        item = DetailMapFootprintItem("d1", "T", "p1", _affine(), 200.0, 100.0)
        br = item.boundingRect()
        assert br.width() == 200.0
        assert br.height() == 100.0

    def test_set_edit_mode_toggles_state(self):
        item = DetailMapFootprintItem("d1", "T", "p1", _affine(), 200.0, 100.0)
        assert not item._edit_mode
        item.set_edit_mode(True)
        assert item._edit_mode
        assert item._pre_edit_registration is not None
        item.set_edit_mode(False)
        assert not item._edit_mode
        assert item._pre_edit_registration is None

    def test_cancel_edit_reverts_registration(self):
        orig = _affine(cx=0.5, cy=0.5, scale=0.25)
        item = DetailMapFootprintItem("d1", "T", "p1", orig, 200.0, 100.0)
        item.set_edit_mode(True)
        item.nudge(0.1, 0.1)  # modifies the registration
        assert item.current_registration()["master_center_norm"]["x"] != 0.5
        item.cancel_edit()
        restored = item.current_registration()
        assert abs(restored["master_center_norm"]["x"] - 0.5) < 1e-9

    def test_nudge_clamps_to_unit_square(self):
        reg = _affine(cx=0.0, cy=0.0)
        item = DetailMapFootprintItem("d1", "T", "p1", reg, 200.0, 100.0)
        item.nudge(-1.0, -1.0)  # try to go negative
        norm = item.current_registration()["master_center_norm"]
        assert norm["x"] == 0.0
        assert norm["y"] == 0.0

    def test_rotate_wraps_at_360(self):
        reg = _affine(rotation=350.0)
        item = DetailMapFootprintItem("d1", "T", "p1", reg, 200.0, 100.0)
        item.rotate(20.0)  # 350 + 20 = 370 → 10
        rot = item.current_registration()["rotation_deg"]
        assert abs(rot - 10.0) < 1e-9

    def test_update_registration_replaces_and_repaints(self):
        item = DetailMapFootprintItem("d1", "T", "p1", _affine(), 200.0, 100.0)
        new_reg = _affine(cx=0.3, cy=0.7, scale=0.4)
        item.update_registration(new_reg)
        assert item.current_registration()["master_center_norm"]["x"] == 0.3

    def test_shape_contains_no_area_on_invalid_registration(self):
        bad_reg = {"mode": "aspect_locked_affine", "scale_norm": 0}  # invalid
        item = DetailMapFootprintItem("d1", "T", "p1", bad_reg, 200.0, 100.0)

        # shape() should not raise even for a degenerate registration
        path = item.shape()
        assert path is not None


# ---------------------------------------------------------------------------
# MapGraphicsView footprint container tests
# ---------------------------------------------------------------------------


class TestMapGraphicsViewFootprints:
    def test_set_footprints_adds_items(self, view):
        data = [
            _make_footprint_data("d1", "City A"),
            _make_footprint_data("d2", "City B", reg=_affine(cx=0.3)),
        ]
        view.set_footprints(data)
        assert len(view._footprint_items) == 2
        assert "d1" in view._footprint_items
        assert "d2" in view._footprint_items

    def test_set_footprints_clears_previous(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.set_footprints([_make_footprint_data("d2")])
        assert "d1" not in view._footprint_items
        assert "d2" in view._footprint_items

    def test_clear_footprints_empties_dict(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        assert len(view._footprint_items) == 1
        view.clear_footprints()
        assert len(view._footprint_items) == 0

    def test_clear_footprints_removes_from_scene(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        item = view._footprint_items["d1"]
        assert item.scene() is not None
        view.clear_footprints()
        assert item.scene() is None

    def test_set_footprints_items_in_scene(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        item = view._footprint_items["d1"]
        assert item.scene() is view.scene

    def test_labels_render_below_footprints(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        item = view._footprint_items["d1"]

        label_rect = item.label_rect()
        footprint_rect = item.footprint_bounds_rect()

        assert label_rect is not None
        assert label_rect.top() >= footprint_rect.bottom()

    def test_labels_avoid_overlap(self, view):
        data = [
            _make_footprint_data("d1", reg=_affine(cx=0.45, cy=0.40, scale=0.22)),
            _make_footprint_data("d2", reg=_affine(cx=0.55, cy=0.40, scale=0.22)),
        ]
        view.set_footprints(data)

        rect1 = view._footprint_items["d1"].label_rect()
        rect2 = view._footprint_items["d2"].label_rect()

        assert rect1 is not None
        assert rect2 is not None
        assert not rect1.intersects(rect2)

    def test_labels_scale_with_zoom(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        item = view._footprint_items["d1"]

        before = item.label_rect()
        assert before is not None

        view.scale(2.0, 2.0)
        view._layout_footprint_labels()

        after = item.label_rect()
        assert after is not None
        assert after.height() > before.height()

    def test_set_footprints_noop_without_pixmap(self, qtbot):
        v = MapGraphicsView()
        qtbot.addWidget(v)
        v.set_footprints([_make_footprint_data("d1")])
        assert len(v._footprint_items) == 0

    def test_set_footprints_visible_false_hides_items(self, view):
        view.set_footprints([_make_footprint_data("d1"), _make_footprint_data("d2")])

        view.set_footprints_visible(False)

        assert view.footprints_visible is False
        assert all(not item.isVisible() for item in view._footprint_items.values())

    def test_set_footprints_visible_false_disables_items(self, view):
        view.set_footprints([_make_footprint_data("d1"), _make_footprint_data("d2")])

        view.set_footprints_visible(False)

        assert all(not item.isEnabled() for item in view._footprint_items.values())

    def test_set_footprints_respects_existing_visibility_state(self, view):
        view.set_footprints_visible(False)

        view.set_footprints([_make_footprint_data("d1")])

        item = view._footprint_items["d1"]
        assert not item.isVisible()
        assert not item.isEnabled()

    def test_detail_map_clicked_signal_propagates(self, view, qtbot):
        """detail_map_clicked from footprint item is re-emitted by the view."""
        view.set_footprints([_make_footprint_data("d1")])
        received: list[str] = []
        view.detail_map_clicked.connect(received.append)
        # Emit directly from the footprint item to isolate signal wiring.
        view._footprint_items["d1"].detail_map_clicked.emit("d1")
        assert received == ["d1"]


# ---------------------------------------------------------------------------
# Edit-mode lifecycle tests
# ---------------------------------------------------------------------------


class TestFootprintEditMode:
    def test_is_editing_footprint_false_initially(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        assert not view.is_editing_footprint

    def test_start_footprint_edit_sets_flag(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("d1")
        assert view.is_editing_footprint
        assert view._editing_footprint_id == "d1"
        assert view._footprint_items["d1"]._edit_mode

    def test_start_footprint_edit_unknown_id_is_noop(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("nonexistent")
        assert not view.is_editing_footprint

    def test_start_footprint_edit_hidden_footprints_is_noop(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.set_footprints_visible(False)

        view.start_footprint_edit("d1")

        assert not view.is_editing_footprint

    def test_finish_footprint_edit_emits_confirmed(self, view, qtbot):
        reg = _affine()
        view.set_footprints([_make_footprint_data("d1", reg=reg)])
        view.start_footprint_edit("d1")
        confirmed: list[tuple] = []
        view.footprint_edit_confirmed.connect(
            lambda d, p, r: confirmed.append((d, p, r))
        )
        view.finish_footprint_edit()
        assert len(confirmed) == 1
        d, p, r = confirmed[0]
        assert d == "d1"
        assert p == "p1"
        assert r == view._footprint_items["d1"].current_registration()

    def test_finish_footprint_edit_clears_flag(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("d1")
        view.finish_footprint_edit()
        assert not view.is_editing_footprint

    def test_cancel_footprint_edit_emits_cancelled(self, view, qtbot):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("d1")
        cancelled: list[int] = []
        view.footprint_edit_cancelled.connect(lambda: cancelled.append(1))
        view.cancel_footprint_edit()
        assert len(cancelled) == 1

    def test_cancel_footprint_edit_reverts_registration(self, view):
        orig = _affine(cx=0.5)
        view.set_footprints([_make_footprint_data("d1", reg=orig)])
        view.start_footprint_edit("d1")
        view._footprint_items["d1"].nudge(0.2, 0.0)
        view.cancel_footprint_edit()
        restored = view._footprint_items["d1"].current_registration()
        assert abs(restored["master_center_norm"]["x"] - 0.5) < 1e-9

    def test_hiding_footprints_cancels_active_edit(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("d1")

        cancelled: list[int] = []
        view.footprint_edit_cancelled.connect(lambda: cancelled.append(1))

        view.set_footprints_visible(False)

        assert not view.is_editing_footprint
        assert cancelled == [1]

    def test_clear_footprints_resets_editing_id(self, view):
        view.set_footprints([_make_footprint_data("d1")])
        view.start_footprint_edit("d1")
        view.clear_footprints()
        assert not view.is_editing_footprint
        assert view._editing_footprint_id is None
