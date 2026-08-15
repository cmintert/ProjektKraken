"""Regression tests for per-marker point-icon sizing."""

import pytest
from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MarkerMapSizeUnit,
    MarkerSizingMode,
    MarkerSizingSettings,
)
from src.core.style_constants import V_SIZE_SCALE
from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.marker_size_dialog import MarkerSizeDialog


def _pixmap_item(width: int = 1000, height: int = 500) -> QGraphicsPixmapItem:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    return QGraphicsPixmapItem(pixmap)


def test_legacy_attributes_default_to_map_relative() -> None:
    settings = MarkerSizingSettings.from_attributes({})

    assert settings.mode is MarkerSizingMode.MAP_RELATIVE
    assert settings.map_unit is MarkerMapSizeUnit.MAP_WIDTH_PERCENT
    assert settings.map_value == 2.5
    assert settings.screen_px == 24.0


def test_invalid_marker_sizing_payload_uses_safe_defaults() -> None:
    settings = MarkerSizingSettings.from_attributes(
        {
            MARKER_SIZING_ATTRIBUTE: {
                "mode": "unknown",
                "map_unit": "parsecs",
                "map_value": -4,
                "screen_px": float("nan"),
            }
        }
    )

    assert settings == MarkerSizingSettings()


def test_percent_marker_size_and_individual_multiplier_apply_once(qapp) -> None:
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Hero",
        _pixmap_item(),
        visual_attributes={V_SIZE_SCALE: 2.0},
    )

    assert marker.resolved_size == 50.0
    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations


def test_metric_marker_size_uses_calibrated_map_width(qapp) -> None:
    settings = MarkerSizingSettings(
        map_unit=MarkerMapSizeUnit.METERS,
        map_value=2.0,
    )
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Hero",
        _pixmap_item(),
        marker_sizing=settings,
        map_width_meters=100.0,
    )

    assert marker.resolved_size == 20.0
    marker.set_map_width_meters(200.0)
    assert marker.resolved_size == 10.0


def test_screen_fixed_marker_keeps_device_sized_geometry(qapp) -> None:
    settings = MarkerSizingSettings(
        mode=MarkerSizingMode.SCREEN_FIXED,
        screen_px=32.0,
    )
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Hero",
        _pixmap_item(),
        marker_sizing=settings,
    )

    assert marker.resolved_size == 32.0
    assert marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    assert marker.label_clearance_px(4.0) == 16.0


def test_map_relative_label_clearance_tracks_view_scale(qapp) -> None:
    marker = MarkerItem("marker-1", "entity", "Hero", _pixmap_item())

    assert marker.resolved_size == 25.0
    assert marker.label_clearance_px(2.0) == 25.0


def test_size_dialog_disables_metric_units_without_calibration(qapp, qtbot) -> None:
    dialog = MarkerSizeDialog(MarkerSizingSettings(), 1.0, 0.0, 1000.0, 1.0)
    qtbot.addWidget(dialog)
    model = dialog.unit_selector.model()

    assert dialog.get_settings() == MarkerSizingSettings()
    assert not model.item(1).isEnabled()
    assert not model.item(2).isEnabled()


def test_size_dialog_converts_percent_to_meters_without_size_jump(
    qapp, qtbot
) -> None:
    dialog = MarkerSizeDialog(MarkerSizingSettings(), 1.0, 1000.0, 1000.0, 1.0)
    qtbot.addWidget(dialog)

    dialog.unit_selector.setCurrentText("m")
    settings = dialog.get_settings()

    assert settings.map_unit is MarkerMapSizeUnit.METERS
    assert settings.map_value == 25.0
    assert "25.00 m" in dialog.summary.text()
    assert "~25 px" in dialog.summary.text()


def test_size_dialog_preserves_relative_and_screen_values(qapp, qtbot) -> None:
    dialog = MarkerSizeDialog(MarkerSizingSettings(), 1.0, 1000.0, 1000.0, 1.0)
    qtbot.addWidget(dialog)
    dialog.size_input.setValue(4.0)

    dialog.mode_selector.setCurrentIndex(
        dialog.mode_selector.findData(MarkerSizingMode.SCREEN_FIXED.value)
    )
    dialog.size_input.setValue(40.0)
    dialog.mode_selector.setCurrentIndex(
        dialog.mode_selector.findData(MarkerSizingMode.MAP_RELATIVE.value)
    )

    assert dialog.size_input.value() == 4.0
    settings = dialog.get_settings()
    assert settings.map_value == 4.0
    assert settings.screen_px == 40.0


def test_view_exposes_minimum_pointer_target_for_tiny_marker(
    qapp, qtbot, monkeypatch
) -> None:
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    qtbot.addWidget(view)
    pixmap_item = _pixmap_item(1000, 500)
    view.pixmap_item = pixmap_item
    view.graphics_scene.addItem(pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 1000, 500))
    settings = MarkerSizingSettings(map_value=0.1)
    view.add_marker(
        "marker-1",
        "entity",
        "Hero",
        0.5,
        0.5,
        visual_attributes={MARKER_SIZING_ATTRIBUTE: settings.to_dict()},
    )
    marker = view.markers["marker-1"]
    center = view.mapFromScene(marker.scenePos())

    assert view._marker_near_view_pos(center + QPoint(9, 0)) is marker
    assert view._marker_near_view_pos(center + QPoint(11, 0)) is None


def test_markers_on_same_map_can_use_different_zoom_behavior(qapp) -> None:
    relative = MarkerItem("relative", "entity", "Hero", _pixmap_item())
    fixed_settings = MarkerSizingSettings(mode=MarkerSizingMode.SCREEN_FIXED)
    fixed = MarkerItem(
        "fixed",
        "entity",
        "Note",
        _pixmap_item(),
        visual_attributes={MARKER_SIZING_ATTRIBUTE: fixed_settings.to_dict()},
    )

    assert not relative.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    assert fixed.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations


def test_large_marker_label_clearance_remains_attached(qapp) -> None:
    marker = MarkerItem("marker-1", "entity", "Hero", _pixmap_item())

    assert marker.label_clearance_px(20.0) == 250.0


@pytest.mark.parametrize("view_scale", [0.2, 1.0, 4.0, 20.0])
def test_map_relative_label_stays_attached_to_rendered_marker(
    qapp, view_scale
) -> None:
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.scale(view_scale, view_scale)
    pixmap_item = _pixmap_item()
    marker = MarkerItem("marker-1", "entity", "Hero", pixmap_item)
    marker.setPos(500.0, 250.0)
    scene.addItem(marker)

    LabelManager().run_layout_pass([marker], view.transform().m11())

    viewport_transform = view.viewportTransform()
    marker_rect = marker.deviceTransform(viewport_transform).mapRect(
        marker.boundingRect()
    )
    label_rect = marker._label_item.deviceTransform(viewport_transform).mapRect(
        marker._label_item.boundingRect()
    )
    gap = label_rect.top() - marker_rect.bottom()

    assert gap == pytest.approx(2.0)


@pytest.mark.parametrize("view_scale", [0.2, 1.0, 4.0, 20.0])
def test_screen_fixed_label_stays_attached_to_rendered_marker(
    qapp, view_scale
) -> None:
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.scale(view_scale, view_scale)
    pixmap_item = _pixmap_item()
    settings = MarkerSizingSettings(
        mode=MarkerSizingMode.SCREEN_FIXED,
        screen_px=32.0,
    )
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Hero",
        pixmap_item,
        marker_sizing=settings,
    )
    marker.setPos(500.0, 250.0)
    scene.addItem(marker)

    LabelManager().run_layout_pass([marker], view.transform().m11())

    viewport_transform = view.viewportTransform()
    marker_rect = marker.deviceTransform(viewport_transform).mapRect(
        marker.boundingRect()
    )
    label_rect = marker._label_item.deviceTransform(viewport_transform).mapRect(
        marker._label_item.boundingRect()
    )
    gap = label_rect.top() - marker_rect.bottom()

    assert gap == pytest.approx(2.0)
