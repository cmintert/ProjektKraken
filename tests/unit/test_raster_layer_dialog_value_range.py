"""Tests for the value-range section in RasterLayerDialog.

Covers the import-time UI that lets the user see / edit the real-world
value range for a continuous raster, pre-filled from inferred metadata
when available.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PilImage
from PIL import TiffImagePlugin
from pytestqt.qtbot import QtBot

from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_geotiff(path: str, smin: float = -4000.0, smax: float = 8000.0) -> None:
    """Write a float GeoTIFF with GDAL_METADATA statistics + UNITTYPE."""
    arr = np.full((8, 8), 1.0, dtype=np.float32)
    extra = TiffImagePlugin.ImageFileDirectory_v2()
    extra[42112] = (
        f'<GDALMetadata>'
        f'<Item name="STATISTICS_MINIMUM">{smin}</Item>'
        f'<Item name="STATISTICS_MAXIMUM">{smax}</Item>'
        f'<Item name="UNITTYPE">metre</Item>'
        f'</GDALMetadata>'
    )
    PilImage.fromarray(arr, mode="F").save(path, tiffinfo=extra)


def _make_plain_png(path: str) -> None:
    """Write a plain PNG with no metadata."""
    arr = np.full((8, 8), 128, dtype=np.uint8)
    PilImage.fromarray(arr, mode="L").save(path)


# ---------------------------------------------------------------------------
# Visibility / mode gating
# ---------------------------------------------------------------------------


def test_value_range_group_exists(qtbot: QtBot) -> None:
    """The dialog must expose a value-range group box."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    assert dlg._value_range_group is not None


def test_value_range_hidden_for_discrete_mode(qtbot: QtBot) -> None:
    """Value-range section stays hidden for discrete mode."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("discrete"))
    assert dlg._value_range_group.isVisible() is False


def test_value_range_visible_for_continuous_mode(qtbot: QtBot) -> None:
    """Value-range section is shown for continuous mode."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg.show()
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("continuous"))
    assert dlg._value_range_group.isVisible() is True
    dlg.close()


def test_value_range_hidden_for_color_mode(qtbot: QtBot) -> None:
    """Value-range section is hidden for color mode (no scalar values)."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("color"))
    assert dlg._value_range_group.isVisible() is False


# ---------------------------------------------------------------------------
# Inference pre-fill
# ---------------------------------------------------------------------------


def test_browse_geotiff_prefills_display_fields(qtbot: QtBot, tmp_path) -> None:
    """Browsing to a GeoTIFF with stats populates min/max/unit fields."""
    path = str(tmp_path / "dem.tif")
    _make_geotiff(path)

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._apply_imported_file(path)

    assert dlg._display_min_edit.text() == "-4000.0"
    assert dlg._display_max_edit.text() == "8000.0"
    assert dlg._display_unit_edit.text() == "metre"


def test_browse_plain_png_leaves_fields_empty(qtbot: QtBot, tmp_path) -> None:
    """A PNG with no metadata leaves the value-range fields blank."""
    path = str(tmp_path / "plain.png")
    _make_plain_png(path)

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._apply_imported_file(path)

    assert dlg._display_min_edit.text() == ""
    assert dlg._display_max_edit.text() == ""
    assert dlg._display_unit_edit.text() == ""


def test_inference_hint_shown_on_prefill(qtbot: QtBot, tmp_path) -> None:
    """When inference fires, a hint label informs the user."""
    path = str(tmp_path / "dem.tif")
    _make_geotiff(path)

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg.show()
    dlg._apply_imported_file(path)

    assert dlg._value_range_hint.isVisible() is True
    assert "inferred" in dlg._value_range_hint.text().lower()
    dlg.close()


# ---------------------------------------------------------------------------
# result_data payload
# ---------------------------------------------------------------------------


def test_result_data_includes_display_fields_when_filled(qtbot: QtBot) -> None:
    """result_data() carries display_min/max/unit when the user filled them."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("continuous"))
    dlg._display_min_edit.setText("-4000")
    dlg._display_max_edit.setText("8000")
    dlg._display_unit_edit.setText("m")

    data = dlg.result_data()
    assert data["display_min"] == pytest.approx(-4000.0)
    assert data["display_max"] == pytest.approx(8000.0)
    assert data["unit"] == "m"


def test_result_data_display_fields_none_when_empty(qtbot: QtBot) -> None:
    """Empty fields yield None / empty string in result_data()."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("continuous"))

    data = dlg.result_data()
    assert data["display_min"] is None
    assert data["display_max"] is None
    assert data["unit"] == ""


def test_result_data_for_discrete_mode_returns_none(qtbot: QtBot) -> None:
    """Discrete mode: display_min/max are always None (ignored downstream)."""
    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData("discrete"))
    # Even if fields have stale text (shouldn't happen via UI, but defensive)
    dlg._display_min_edit.setText("99")
    dlg._display_max_edit.setText("100")

    data = dlg.result_data()
    assert data["display_min"] is None
    assert data["display_max"] is None


def test_user_can_override_inferred_values(qtbot: QtBot, tmp_path) -> None:
    """User can edit pre-filled fields before accepting."""
    path = str(tmp_path / "dem.tif")
    _make_geotiff(path)

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._apply_imported_file(path)

    # Simulate user edit
    dlg._display_min_edit.setText("0")
    dlg._display_max_edit.setText("100")
    dlg._display_unit_edit.setText("ft")

    data = dlg.result_data()
    assert data["display_min"] == pytest.approx(0.0)
    assert data["display_max"] == pytest.approx(100.0)
    assert data["unit"] == "ft"
