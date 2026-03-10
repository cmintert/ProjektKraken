"""Tests for naming precedence in Raster Stats and Legend.

Covers the precedence order: Entity/Event Name > Label > Value/UUID fallback.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication, QWidget

from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer
from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget


# ── Helpers ────────────────────────────────────────────────────────────────


def test_coverage_stats_precedence() -> None:
    """Test CoverageStats naming precedence."""
    # Create simple buffer with values 1, 2, 3
    data = np.array([[1, 2], [3, 0]], dtype=np.uint16)
    buffer = MapDataBuffer(2, 2, data)

    color_map = ColorMap.from_dict(
        {
            "type": "palette",
            "entries": [
                {
                    "value": 1,
                    "color": "#110000",
                    "entity_id": "eid-1",
                },
                {
                    "value": 2,
                    "color": "#220000",
                    "entity_id": "eid-2",
                },
                {"value": 3, "color": "#330000", "entity_id": "eid-3"},
                {
                    "value": 4,
                    "color": "#440000",
                    "entity_id": "",
                },  # Not in array, shouldn't appear
            ],
        }
    )

    vem = {
        "mode": "exact",
        "mappings": [
            {"value": 1, "label": "Label for 1", "entity_id": "eid-1"},
            {"value": 2, "label": "Label for 2", "entity_id": "eid-2"},
            {"value": 3, "label": "", "entity_id": "eid-3"},
        ],
    }

    name_map = {
        "eid-1": "Wolf Pack",  # Has name, label, and eid
        # eid-2 has label, no name
        # eid-3 has only eid, no label, no name
        # value 0 has nothing
    }

    stats = buffer.compute_coverage_stats(color_map, vem, name_map)

    assert stats.mode == "discrete"
    labels_by_value = {c.value: c.label for c in stats.classes}

    assert labels_by_value[1] == "Wolf Pack"  # Entity Name wins
    assert labels_by_value[2] == "Label for 2"  # Label wins
    assert labels_by_value[3] == "eid-3"  # UUID fallback


def test_legend_widget_precedence(qtbot) -> None:
    """Test RasterLegendWidget naming precedence."""
    legend = RasterLegendWidget()
    qtbot.addWidget(legend)

    layer_meta = {
        "name": "Test Layer",
        "color_map": {
            "type": "palette",
            "entries": [
                {
                    "value": 1,
                    "color": "#110000",
                    "label": "VEM Label should override this",
                },
                {"value": 2, "color": "#220000"},
                {"value": 3, "color": "#330000"},
                {"value": 4, "color": "#440000"},
            ],
        },
        "value_entity_map": {
            "mappings": [
                {"value": 1, "label": "V1 Label", "entity_id": "eid-1"},
                {"value": 2, "label": "V2 Label", "entity_id": "eid-2"},
                {"value": 3, "label": "", "entity_id": "eid-3"},
            ]
        },
    }

    name_map = {
        "eid-1": "Entity 1 Real Name",
        # eid-2 has no name, but has label
        # eid-3 has no name and no label, just eid
    }

    legend.set_layer(layer_meta, name_map)

    # Extract labels from the UI
    ui_labels = [
        legend._content_layout.itemAt(i).widget().text()
        for i in range(legend._content_layout.count())
        if hasattr(legend._content_layout.itemAt(i).widget(), "text")
        and legend._content_layout.itemAt(i).widget().text() != "Test Layer"
    ]

    assert "Entity 1 Real Name" in ui_labels
    assert "V2 Label" in ui_labels
    assert "eid-3" in ui_labels
    assert "Value 4" in ui_labels  # Absolute fallback
