"""Unit tests for LabelManager (Greedy PAL-Lite label engine)."""

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.marker_item import MarkerItem


@pytest.fixture
def label_manager():
    """Provides a fresh LabelManager instance."""
    return LabelManager()


@pytest.fixture
def mock_pixmap_item(qapp):
    """Provides a mock pixmap item for markers."""
    return QGraphicsPixmapItem()


def _make_marker(
    pixmap_item, marker_id="m1", label="Test", connection_count=0
):
    """Helper to create a MarkerItem with a given connection_count."""
    marker = MarkerItem(
        marker_id=marker_id,
        object_type="entity",
        label=label,
        pixmap_item=pixmap_item,
    )
    marker.connection_count = connection_count
    return marker


class TestLabelManagerInit:
    """Tests for LabelManager initialization."""

    def test_init_empty(self, label_manager):
        """LabelManager starts with no occupied rects."""
        assert label_manager._occupied_rects == []


class TestIsSpaceFree:
    """Tests for the internal collision detection."""

    def test_empty_space_is_free(self, label_manager):
        """Space is free when no rects are occupied."""
        assert label_manager._is_space_free(QRectF(0, 0, 50, 20)) is True

    def test_overlapping_space_not_free(self, label_manager):
        """Space is not free when it overlaps an occupied rect."""
        label_manager._occupied_rects.append(QRectF(10, 10, 50, 20))
        assert label_manager._is_space_free(QRectF(20, 15, 30, 10)) is False

    def test_adjacent_space_is_free(self, label_manager):
        """Space is free when adjacent but not overlapping."""
        label_manager._occupied_rects.append(QRectF(0, 0, 50, 20))
        # Placed right below without overlap
        assert label_manager._is_space_free(QRectF(0, 20, 50, 20)) is True


class TestRunLayoutPass:
    """Tests for the full layout pass."""

    def test_empty_markers(self, label_manager):
        """Layout pass on empty list does nothing."""
        label_manager.run_layout_pass([], 1.0)
        assert label_manager._occupied_rects == []

    def test_single_marker_gets_visible_label(
        self, label_manager, mock_pixmap_item
    ):
        """A single marker with no competitors should get a visible label."""
        marker = _make_marker(mock_pixmap_item)
        label_manager.run_layout_pass([marker], 1.0)
        assert marker._label_item.isVisible() is True

    def test_single_marker_label_position_nonzero(
        self, label_manager, mock_pixmap_item
    ):
        """After layout, the label should not be at the default (0, 0)."""
        marker = _make_marker(mock_pixmap_item)
        label_manager.run_layout_pass([marker], 1.0)
        pos = marker._label_item.pos()
        # At least one coordinate should be non-zero (placed at a candidate)
        assert pos.x() != 0.0 or pos.y() != 0.0

    def test_priority_sorting_high_count_first(
        self, label_manager, mock_pixmap_item
    ):
        """Higher connection_count markers should be laid out first."""
        m_low = _make_marker(
            mock_pixmap_item, "low", "Low", connection_count=1
        )
        m_high = _make_marker(
            mock_pixmap_item, "high", "High", connection_count=10
        )

        # Place them at the same spot to force competition
        m_low.setPos(100, 100)
        m_high.setPos(100, 100)

        label_manager.run_layout_pass([m_low, m_high], 1.0)

        # The high-priority marker should always get a visible label
        assert m_high._label_item.isVisible() is True

    def test_clears_previous_rects(
        self, label_manager, mock_pixmap_item
    ):
        """Each layout pass starts fresh (no stale rects)."""
        marker = _make_marker(mock_pixmap_item)
        label_manager.run_layout_pass([marker], 1.0)
        occupied_count_first = len(label_manager._occupied_rects)

        # Run again — should not accumulate
        label_manager.run_layout_pass([marker], 1.0)
        occupied_count_second = len(label_manager._occupied_rects)

        assert occupied_count_second == occupied_count_first

    def test_zero_view_scale_handled(
        self, label_manager, mock_pixmap_item
    ):
        """A view_scale of 0 should not cause ZeroDivisionError."""
        marker = _make_marker(mock_pixmap_item)
        # Should not raise
        label_manager.run_layout_pass([marker], 0.0)

    def test_multiple_separated_markers_all_visible(
        self, label_manager, mock_pixmap_item
    ):
        """Markers placed far apart should all get visible labels."""
        markers = []
        for i in range(5):
            m = _make_marker(
                mock_pixmap_item, f"m{i}", f"Label {i}"
            )
            m.setPos(i * 200, 0)  # Far apart
            markers.append(m)

        label_manager.run_layout_pass(markers, 1.0)

        visible_count = sum(
            1 for m in markers if m._label_item.isVisible()
        )
        assert visible_count == 5
