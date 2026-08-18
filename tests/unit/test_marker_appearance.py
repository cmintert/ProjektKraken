"""Tests for copyable marker appearance, anchors, and direct resizing."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene

from src.commands.marker_commands import ApplyMarkerAppearanceCommand
from src.core.map import Map
from src.core.marker import Marker
from src.core.marker_appearance import (
    MARKER_ICON_ANCHOR_ATTRIBUTE,
    MarkerAppearance,
    MarkerIconAnchor,
)
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MarkerMapSizeUnit,
    MarkerSizingMode,
    MarkerSizingSettings,
)
from src.core.style_constants import V_BORDER, V_FILL, V_SIZE_SCALE
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem
from src.services.db_service import DatabaseService


def _pixmap_item() -> QGraphicsPixmapItem:
    pixmap = QPixmap(1000, 500)
    pixmap.fill()
    return QGraphicsPixmapItem(pixmap)


def _marker(attributes: dict | None = None) -> MarkerItem:
    return MarkerItem(
        "marker-1",
        "entity",
        "Harbour",
        _pixmap_item(),
        visual_attributes=attributes,
    )


def test_appearance_replaces_only_allowlisted_keys() -> None:
    source = MarkerAppearance.from_attributes(
        {
            "icon": "castle.svg",
            V_FILL: "#FF0000",
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0},
        }
    )

    result = source.apply_to_attributes(
        {
            "semantic_note": "keep me",
            V_BORDER: "#00FF00",
            MARKER_SIZING_ATTRIBUTE: {"mode": "screen_fixed"},
        }
    )

    assert result["semantic_note"] == "keep me"
    assert result["icon"] == "castle.svg"
    assert result[V_FILL] == "#FF0000"
    assert V_BORDER not in result
    assert MARKER_SIZING_ATTRIBUTE not in result
    assert result[MARKER_ICON_ANCHOR_ATTRIBUTE] == {"x": 0.5, "y": 1.0}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"x": -5, "y": 8}, MarkerIconAnchor(0.0, 1.0)),
        ({"x": "bad", "y": None}, MarkerIconAnchor()),
        ({"x": 0.25, "y": 0.75}, MarkerIconAnchor(0.25, 0.75)),
    ],
)
def test_anchor_values_are_validated(payload: dict, expected: MarkerIconAnchor) -> None:
    assert MarkerIconAnchor.from_dict(payload) == expected


def test_apply_appearance_command_removes_stale_overrides_and_undoes() -> None:
    database = MagicMock(spec=DatabaseService)
    original = Marker(
        map_id="map-1",
        object_id="object-1",
        object_type="entity",
        x=0.5,
        y=0.5,
        id="marker-1",
        attributes={"note": "preserve", V_BORDER: "#00FF00"},
    )
    database.get_marker.return_value = original
    command = ApplyMarkerAppearanceCommand(
        "marker-1",
        {
            "icon": "castle.svg",
            V_FILL: "#FF0000",
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0},
        },
    )

    result = command.execute(database)

    assert result.success
    applied = database.insert_marker.call_args.args[0]
    assert applied.attributes["note"] == "preserve"
    assert applied.attributes["icon"] == "castle.svg"
    assert V_BORDER not in applied.attributes

    command.undo(database)
    restored = database.insert_marker.call_args.args[0]
    assert restored.attributes == original.attributes


def test_appearance_command_roundtrip_serialization() -> None:
    command = ApplyMarkerAppearanceCommand(
        "marker-1",
        {
            V_FILL: "#FF0000",
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.25, "y": 0.75},
        },
    )

    restored = ApplyMarkerAppearanceCommand.from_dict(command.to_dict())

    assert restored.marker_id == "marker-1"
    assert restored.appearance == command.appearance


def test_appearance_survives_database_reload(db_service) -> None:
    map_object = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_object)
    marker = Marker(
        map_id=map_object.id,
        object_id="object-1",
        object_type="entity",
        x=0.5,
        y=0.5,
        attributes={"note": "preserve", V_BORDER: "#00FF00"},
    )
    db_service.insert_marker(marker)
    command = ApplyMarkerAppearanceCommand(
        marker.id,
        {
            "icon": "castle.svg",
            V_SIZE_SCALE: 1.75,
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0},
        },
    )

    assert command.execute(db_service).success
    reloaded = db_service.get_marker(marker.id)

    assert reloaded is not None
    assert reloaded.attributes["note"] == "preserve"
    assert reloaded.attributes["icon"] == "castle.svg"
    assert reloaded.attributes[V_SIZE_SCALE] == 1.75
    assert reloaded.attributes[MARKER_ICON_ANCHOR_ATTRIBUTE] == {
        "x": 0.5,
        "y": 1.0,
    }


def test_bottom_anchor_offsets_bounds_around_fixed_map_coordinate(qapp) -> None:
    marker = _marker(
        {MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0}}
    )

    rect = marker.boundingRect()

    assert rect.width() == pytest.approx(15.0)
    assert rect.left() == pytest.approx(-7.5)
    assert rect.top() == pytest.approx(-15.0)
    assert rect.bottom() == pytest.approx(0.0)


def test_label_obstacle_uses_asymmetric_rendered_bounds(qapp) -> None:
    marker = _marker(
        {MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.0, "y": 0.0}}
    )
    marker.setPos(100.0, 200.0)

    obstacle = marker.label_obstacle_scene_rect(4.0)

    assert obstacle.left() == pytest.approx(100.0)
    assert obstacle.top() == pytest.approx(200.0)
    assert obstacle.right() == pytest.approx(115.0)
    assert obstacle.bottom() == pytest.approx(215.0)


def test_direct_resize_previews_then_returns_one_payload(qapp) -> None:
    scene = QGraphicsScene()
    marker = _marker()
    scene.addItem(marker)
    marker.begin_appearance_edit()
    corner = marker.boundingRect().bottomRight()

    marker._resize_handle.setPos(QPointF(corner.x() * 2.0, corner.y() * 2.0))
    assert marker._resize_handle.pos() == marker.boundingRect().bottomRight()
    payload = marker.finish_appearance_edit()

    assert payload is not None
    assert payload[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(3.0)
    assert not marker.is_editing_appearance


def test_direct_resize_updates_fixed_screen_size(qapp) -> None:
    scene = QGraphicsScene()
    marker = _marker(
        {
            MARKER_SIZING_ATTRIBUTE: MarkerSizingSettings(
                mode=MarkerSizingMode.SCREEN_FIXED,
                screen_px=24.0,
            ).to_dict()
        }
    )
    scene.addItem(marker)
    marker.begin_appearance_edit()
    corner = marker.boundingRect().bottomRight()

    marker._resize_handle.setPos(QPointF(corner.x() * 2.0, corner.y() * 2.0))
    payload = marker.finish_appearance_edit()

    assert payload is not None
    assert payload[MARKER_SIZING_ATTRIBUTE]["screen_px"] == pytest.approx(48.0)


def test_direct_resize_updates_metric_footprint_beyond_one_hundred_meters(qapp) -> None:
    scene = QGraphicsScene()
    settings = MarkerSizingSettings(
        map_unit=MarkerMapSizeUnit.METERS,
        map_value=1000.0,
    )
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Harbour",
        _pixmap_item(),
        visual_attributes={MARKER_SIZING_ATTRIBUTE: settings.to_dict()},
        map_width_meters=10_000.0,
    )
    scene.addItem(marker)
    marker.begin_appearance_edit()
    corner = marker.boundingRect().bottomRight()

    marker._resize_handle.setPos(QPointF(corner.x() * 2.0, corner.y() * 2.0))
    payload = marker.finish_appearance_edit()

    assert payload is not None
    assert payload[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(2000.0)


def test_direct_anchor_edit_and_cancel_are_local(qapp) -> None:
    scene = QGraphicsScene()
    marker = _marker({V_FILL: "#FF0000"})
    scene.addItem(marker)
    marker.begin_appearance_edit()
    rect = marker.boundingRect()
    marker._anchor_handle.setPos(rect.bottomRight())

    marker.cancel_appearance_edit()

    assert marker._visual_attributes == {V_FILL: "#FF0000"}
    assert not marker.is_editing_appearance


def test_direct_anchor_edit_commits_normalized_candidate(qapp) -> None:
    scene = QGraphicsScene()
    marker = _marker()
    scene.addItem(marker)
    marker.begin_appearance_edit()
    marker._anchor_handle.setPos(marker.boundingRect().bottomRight())

    payload = marker.finish_appearance_edit()

    assert payload is not None
    assert payload[MARKER_ICON_ANCHOR_ATTRIBUTE] == {"x": 1.0, "y": 1.0}


def test_view_emits_one_appearance_change_only_on_confirm(
    qapp, qtbot, monkeypatch
) -> None:
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    qtbot.addWidget(view)
    pixmap_item = _pixmap_item()
    view.pixmap_item = pixmap_item
    view.graphics_scene.addItem(pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0.0, 0.0, 1000.0, 500.0))
    view.add_marker("marker-1", "entity", "Harbour", 0.5, 0.5)
    emitted: list[tuple[str, dict]] = []
    view.marker_appearance_changed.connect(
        lambda marker_id, payload: emitted.append((marker_id, payload))
    )

    view.start_marker_appearance_edit("marker-1")
    marker = view.markers["marker-1"]
    corner = marker.boundingRect().bottomRight()
    marker._resize_handle.setPos(QPointF(corner.x() * 1.5, corner.y() * 1.5))
    assert emitted == []
    view.finish_marker_appearance_edit()

    assert len(emitted) == 1
    assert emitted[0][0] == "marker-1"
    assert emitted[0][1][MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(2.25)

    view.start_marker_appearance_edit("marker-1")
    marker._resize_handle.setPos(QPointF(corner.x() * 2.0, corner.y() * 2.0))
    view.cancel_marker_appearance_edit()

    assert len(emitted) == 1
    assert marker._visual_attributes[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(
        2.25
    )


def test_interaction_copy_paste_replaces_only_marker_appearance(
    qapp, qtbot, monkeypatch
) -> None:
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    qtbot.addWidget(view)
    pixmap_item = _pixmap_item()
    view.pixmap_item = pixmap_item
    view.graphics_scene.addItem(pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0.0, 0.0, 1000.0, 500.0))
    view.add_marker(
        "source",
        "entity",
        "Source",
        0.25,
        0.5,
        icon="castle.svg",
        visual_attributes={
            "icon": "castle.svg",
            V_FILL: "#FF0000",
            V_SIZE_SCALE: 1.5,
            MARKER_SIZING_ATTRIBUTE: MarkerSizingSettings(map_value=3.0).to_dict(),
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0},
        },
    )
    view.add_marker(
        "target",
        "entity",
        "Target",
        0.75,
        0.5,
        visual_attributes={"note": "keep", V_BORDER: "#00FF00"},
    )
    emitted: list[tuple[str, dict]] = []
    view.marker_appearance_changed.connect(
        lambda marker_id, payload: emitted.append((marker_id, payload))
    )

    view._interaction._copy_marker_appearance(view.markers["source"])
    view._interaction._paste_marker_appearance(view.markers["target"])

    target = view.markers["target"]
    assert target._visual_attributes["note"] == "keep"
    assert target._visual_attributes["icon"] == "castle.svg"
    assert target._visual_attributes[V_FILL] == "#FF0000"
    assert V_BORDER not in target._visual_attributes
    assert target._visual_attributes[MARKER_SIZING_ATTRIBUTE]["map_value"] == 3.0
    assert emitted == [("target", view.markers["source"].appearance_payload())]


def test_edit_handles_win_hit_testing_and_never_move_marker(
    qapp, qtbot, monkeypatch
) -> None:
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    pixmap_item = _pixmap_item()
    view.pixmap_item = pixmap_item
    view.graphics_scene.addItem(pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0.0, 0.0, 1000.0, 500.0))
    view.add_marker("marker-1", "entity", "Harbour", 0.5, 0.5)
    view.show()
    view.centerOn(view.markers["marker-1"])
    qapp.processEvents()
    view.start_marker_appearance_edit("marker-1")
    marker = view.markers["marker-1"]
    original_position = QPointF(marker.pos())
    moved: list[tuple[str, float, float]] = []
    view.marker_moved.connect(
        lambda marker_id, x, y: moved.append((marker_id, x, y))
    )

    resize_position = view.mapFromScene(marker._resize_handle.scenePos())
    anchor_position = view.mapFromScene(marker._anchor_handle.scenePos())
    assert view.itemAt(resize_position) is marker._resize_handle
    assert view.itemAt(anchor_position) is marker._anchor_handle

    qtbot.mousePress(
        view.viewport(), Qt.MouseButton.LeftButton, pos=anchor_position
    )
    qtbot.mouseMove(view.viewport(), pos=anchor_position + QPoint(10, 10))
    qtbot.mouseRelease(
        view.viewport(), Qt.MouseButton.LeftButton, pos=anchor_position + QPoint(10, 10)
    )

    assert marker.pos() == original_position
    assert moved == []
