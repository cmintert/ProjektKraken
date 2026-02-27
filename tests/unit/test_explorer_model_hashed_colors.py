"""Tests for ExplorerModel hashed coloring."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush

from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel


class TestExplorerModelHashedColors:
    """Tests for hashed coloring feature in ExplorerModel."""

    @pytest.fixture
    def model(self):
        """Returns a configured ExplorerModel."""
        m = ExplorerModel()
        return m

    def test_hashed_colors_disabled_by_default(self, model):
        """Verify the model does not use hashed colors by default."""
        assert model._use_hashed_colors is False

    def test_set_use_hashed_colors_emits_data_changed(self, model):
        """Verify toggling the feature emits a dataChanged signal to repaint items."""
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        model.set_items([("event", event1)])

        mock_slot = MagicMock()
        model.dataChanged.connect(mock_slot)

        model.set_use_hashed_colors(True)

        assert model._use_hashed_colors is True
        mock_slot.assert_called_once()

        args, _ = mock_slot.call_args
        assert args[2] == [Qt.ItemDataRole.ForegroundRole]

    def test_hashed_colors_generate_stable_hues(self, model):
        """Verify _get_hashed_color produces consistent colors for the same string."""
        brush1 = model._get_hashed_color("Character: Castro")
        brush2 = model._get_hashed_color("Character: Castro")

        assert isinstance(brush1, QBrush)
        assert brush1.color().name() == brush2.color().name()

    def test_hashed_colors_vary_by_name(self, model):
        """Verify different strings generate different colors."""
        brush1 = model._get_hashed_color("Item: Sword")
        brush2 = model._get_hashed_color("Location: Castle")

        assert brush1.color().name() != brush2.color().name()

    def test_data_returns_hashed_color_when_enabled(self, model):
        """Verify data returns the hashed color when enabled."""
        event1 = Event(id="e1", name="Alpha Test", lore_date=100)
        model.set_items([("event", event1)])

        index = model.index(0, 0)

        # Default colors
        default_brush = model.data(index, Qt.ItemDataRole.ForegroundRole)

        # Enable hashing
        model.set_use_hashed_colors(True)
        hashed_brush = model.data(index, Qt.ItemDataRole.ForegroundRole)

        # Get expected hash (the model uses "item_type:item_name" as the seed)
        expected_brush = model._get_hashed_color("event:Alpha Test")

        assert hashed_brush.color().name() == expected_brush.color().name()
        assert hashed_brush.color().name() != default_brush.color().name()
