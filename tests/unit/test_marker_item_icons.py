"""Tests for bundled and portable-world map marker icons."""

import os
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.marker_appearance import (
    MARKER_ICON_ANCHOR_ATTRIBUTE,
    MarkerIconAnchor,
)
from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSettings,
    MarkerSizingSource,
)
from src.gui.widgets.map.interaction_handler import InteractionHandler
from src.gui.widgets.map.marker_item import MarkerItem


def _write_raster(path: Path) -> None:
    mode = "RGB" if path.suffix.lower() in {".jpg", ".jpeg"} else "RGBA"
    color = (220, 40, 30) if mode == "RGB" else (220, 40, 30, 128)
    Image.new(mode, (40, 20), color).save(path)


def _marker(world_root: Path, icon: str) -> MarkerItem:
    return MarkerItem(
        marker_id="marker-1",
        object_type="event",
        label="Marker",
        pixmap_item=QGraphicsPixmapItem(),
        icon=icon,
        world_root=str(world_root),
    )


@pytest.mark.parametrize("extension", [".png", ".jpg", ".jpeg", ".webp"])
def test_project_raster_icon_loads(qapp, tmp_path, extension):
    """Every supported raster format loads from portable world assets."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    icon_path = icon_dir / f"icon_test{extension}"
    _write_raster(icon_path)

    marker = _marker(tmp_path, f"assets/images/{icon_path.name}")

    assert marker.is_raster_icon
    assert marker._raster_pixmap is not None
    assert marker._raster_pixmap.width() == 40
    assert marker._raster_pixmap.height() == 20


def test_project_svg_icon_loads(qapp, tmp_path):
    """Project SVGs resolve against the active portable world."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    icon_path = icon_dir / "icon_test.svg"
    icon_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
        '<circle cx="10" cy="10" r="8" fill="#ffffff"/></svg>',
        encoding="utf-8",
    )

    marker = _marker(tmp_path, "assets/images/icon_test.svg")

    assert not marker.is_raster_icon
    assert marker._svg_renderer is not None
    assert marker._svg_renderer.isValid()


def test_raster_icon_paints_centered_with_preserved_aspect_ratio(qapp, tmp_path):
    """Raster artwork is fitted rather than stretched into a square."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    _write_raster(icon_dir / "icon_test.png")
    marker = _marker(tmp_path, "assets/images/icon_test.png")
    canvas = QImage(80, 80, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.translate(40, 40)
    marker.paint(painter, QStyleOptionGraphicsItem())
    painter.end()

    visible = [
        (x, y)
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y).alpha() > 0
    ]
    left = min(x for x, _ in visible)
    right = max(x for x, _ in visible)
    top = min(y for _, y in visible)
    bottom = max(y for _, y in visible)

    assert (right - left + 1) > (bottom - top + 1)
    assert abs((left + right) / 2.0 - 40.0) <= 1.0
    assert abs((top + bottom) / 2.0 - 40.0) <= 1.0


def test_raster_anchor_uses_actual_aspect_preserved_artwork(qapp, tmp_path):
    """Bottom-centre anchors are measured against visible raster artwork."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    _write_raster(icon_dir / "icon_test.png")
    marker = _marker(tmp_path, "assets/images/icon_test.png")
    marker.set_visual_attributes(
        {MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0}}
    )

    rect = marker.boundingRect()

    assert rect.width() == pytest.approx(24.0)
    assert rect.height() == pytest.approx(12.0)
    assert rect.bottom() == pytest.approx(0.0)


def test_svg_rendered_symbol_rect_preserves_viewbox_aspect(qapp, tmp_path):
    """SVG artwork uses its own aspect ratio instead of a square slot."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    (icon_dir / "icon_wide.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
        '<rect width="40" height="20"/></svg>',
        encoding="utf-8",
    )
    marker = _marker(tmp_path, "assets/images/icon_wide.svg")

    rect = marker.rendered_symbol_rect()

    assert rect.width() == pytest.approx(24.0)
    assert rect.height() == pytest.approx(12.0)


def test_definition_anchor_is_used_without_marker_override(qapp, tmp_path):
    definition = MarkerIconDefinition(
        id="test.pin",
        name="Test Pin",
        asset_path="map-pin.svg",
        source=MarkerIconSource.DEFAULT,
        anchor=MarkerIconAnchor(0.5, 1.0),
    )
    marker = MarkerItem(
        "marker-1",
        "entity",
        "Marker",
        QGraphicsPixmapItem(),
        icon="map-pin.svg",
        icon_definition=definition,
    )

    assert marker.rendered_symbol_rect().bottom() == pytest.approx(0.0)


def test_icon_default_size_changes_only_for_following_marker(qapp):
    definition = MarkerIconDefinition(
        id="test.small",
        name="Small",
        asset_path="map-pin.svg",
        source=MarkerIconSource.DEFAULT,
        default_native_diameter_px=30.0,
    )
    pixmap = QPixmap(1000, 500)
    pixmap.fill()
    pixmap_item = QGraphicsPixmapItem(pixmap)
    following = MarkerItem(
        "following",
        "entity",
        "Following",
        pixmap_item,
        visual_attributes={
            MARKER_SIZING_SOURCE_ATTRIBUTE: MarkerSizingSource.ICON_DEFAULT.value
        },
    )
    custom = MarkerItem(
        "custom",
        "entity",
        "Custom",
        pixmap_item,
        visual_attributes={
            MARKER_SIZING_ATTRIBUTE: MarkerSizingSettings(map_value=7.0).to_dict(),
            MARKER_SIZING_SOURCE_ATTRIBUTE: MarkerSizingSource.CUSTOM.value,
        },
    )

    following_updates = InteractionHandler._icon_definition_updates(
        following, definition
    )
    custom_updates = InteractionHandler._icon_definition_updates(custom, definition)

    assert following_updates[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(
        3.0
    )
    assert MARKER_SIZING_ATTRIBUTE not in custom_updates


def test_malformed_raster_uses_fallback(qapp, tmp_path):
    """Unreadable raster files do not retain or expose a pixmap."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    (icon_dir / "icon_broken.png").write_bytes(b"not an image")

    marker = _marker(tmp_path, "assets/images/icon_broken.png")

    assert marker._raster_pixmap is None
    assert marker._svg_renderer is None
    assert not marker.is_raster_icon


def test_bundled_svg_still_loads(qapp, tmp_path):
    """Bare SVG filenames continue to resolve from bundled resources."""
    marker = _marker(tmp_path, "map-pin.svg")

    assert marker._svg_renderer is not None
    assert marker._svg_renderer.isValid()


@pytest.mark.parametrize(
    "icon",
    [
        "../outside.png",
        "assets/images/../../outside.png",
        "C:/outside.png",
        "//server/share/icon.png",
        "nested/default.svg",
    ],
)
def test_untrusted_icon_paths_are_rejected(qapp, tmp_path, icon):
    """Persisted icon identifiers cannot read outside trusted icon roots."""
    marker = _marker(tmp_path, icon)

    assert marker._svg_renderer is None
    assert marker._raster_pixmap is None
    assert not marker.is_raster_icon


def test_project_icon_symlink_escape_is_rejected(qapp, tmp_path):
    """A project asset symlink cannot escape the portable world."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside.png"
    _write_raster(outside)
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    link = icon_dir / "icon_link.png"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this Windows environment")

    marker = _marker(tmp_path, "assets/images/icon_link.png")

    assert not marker.is_raster_icon
    assert marker._raster_pixmap is None


def test_icon_switching_clears_stale_renderer_state(qapp, tmp_path):
    """Raster, SVG, and broken transitions never retain old artwork."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    _write_raster(icon_dir / "icon_test.png")
    marker = _marker(tmp_path, "assets/images/icon_test.png")
    assert marker.is_raster_icon

    marker.set_icon("map-pin.svg")
    assert marker._raster_pixmap is None
    assert marker._svg_renderer is not None

    marker.set_icon("assets/images/icon_missing.png")
    assert marker.get_icon() == "assets/images/icon_missing.png"
    assert marker._raster_pixmap is None
    assert marker._svg_renderer is None


def test_raster_marker_disables_vector_style_actions(qapp, tmp_path):
    """Raster markers retain scale while vector-only actions are disabled."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    _write_raster(icon_dir / "icon_test.png")
    marker = _marker(tmp_path, "assets/images/icon_test.png")
    view = QWidget()
    scale_action = QAction("Set Scale...", view)
    vector_actions = tuple(
        QAction(text, view)
        for text in (
            "Set Border Strength...",
            "Set Fill Color...",
            "Set Border Color...",
            "No Fill (Transparent)",
            "No Border",
        )
    )

    InteractionHandler._configure_vector_style_actions(marker, vector_actions)

    assert all(not action.isEnabled() for action in vector_actions)
    assert scale_action.isEnabled()
