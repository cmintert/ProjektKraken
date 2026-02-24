"""Tests for immediate lexicon propagation (TDD)."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from src.gui.dialogs.lexicon_editor_dialog import LexiconEditorDialog, _ColorButton
from src.gui.widgets.graph_view.graph_widget import GraphWidget


@pytest.fixture
def qapp():
    """Provides a QApplication instance for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestLexiconPropagation:
    """Tests for immediate propagation of lexicon changes."""

    def test_color_button_has_signal(self, qapp):
        """Verify _ColorButton has a color_changed signal."""
        from PySide6.QtGui import QColor

        btn = _ColorButton(QColor("red"))
        assert hasattr(btn, "color_changed")

    def test_dialog_emits_config_changed_on_color_change(self, qapp):
        """Verify LexiconEditorDialog emits config_changed when color changes."""
        dialog = LexiconEditorDialog(entity_types=["hero"])

        # Mock the signal receiver
        mock_slot = MagicMock()
        if hasattr(dialog, "config_changed"):
            dialog.config_changed.connect(mock_slot)
        else:
            pytest.fail("LexiconEditorDialog missing config_changed signal")

        # Simulate color change
        row = dialog._node_rows["hero"]
        color_btn = row["color"]

        # We need to simulate the signal emission from the button if we can't click it
        # But first let's see if the button even has the signal
        if hasattr(color_btn, "color_changed"):
            # Use set_color to ensure internal state is updated too
            if hasattr(color_btn, "set_color"):
                color_btn.set_color("#123456")
            else:
                # Fallback if set_color missing
                color_btn.color_changed.emit("#123456")

            mock_slot.assert_called()
            # Verify payload structure
            args = mock_slot.call_args[0][0]
            assert args["nodes"]["hero"]["color"].lower() == "#123456"
        else:
            pytest.fail("_ColorButton missing color_changed signal")

    def test_dialog_emits_config_changed_on_shape_change(self, qapp):
        """Verify LexiconEditorDialog emits config_changed when shape changes."""
        dialog = LexiconEditorDialog(entity_types=["hero"])
        mock_slot = MagicMock()
        if hasattr(dialog, "config_changed"):
            dialog.config_changed.connect(mock_slot)

        row = dialog._node_rows["hero"]
        combo = row["shape"]

        # Simulate change
        combo.setCurrentIndex(1)  # Change from default

        # This might not trigger signal automatically depending on implementation
        # The test expects immediate propagation
        if mock_slot.called:
            args = mock_slot.call_args[0][0]
            assert args["nodes"]["hero"]["shape"] == combo.currentText()
        else:
            # If not connected yet, this will fail as expected in TDD
            pytest.fail("Signal not emitted on shape change")

    def test_dialog_save_renamed_to_ok(self, qapp):
        """Verify the Save button is renamed to OK."""
        dialog = LexiconEditorDialog()
        # Find the button box
        btn_box = dialog.findChild(QDialogButtonBox)
        save_btn = btn_box.button(QDialogButtonBox.StandardButton.Save)
        assert save_btn.text() == "OK"

    def test_graph_widget_updates_on_preview(self, qapp):
        """Verify GraphWidget updates its internal state when preview requested."""
        graph = GraphWidget()

        # Mock the renderer to avoid actual web view calls
        graph._refresh_display_locally = MagicMock()

        # Create a dummy config
        new_config = {"nodes": {"hero": {"color": "#FFFFFF"}}, "edges": {}}

        # Simulate the slot call (we assume the method exists)
        if hasattr(graph, "_on_lexicon_preview_requested"):
            graph._on_lexicon_preview_requested(new_config)

            # Verify internal state updated
            assert graph._raw_lexicon == new_config
            # Verify refresh called
            graph._refresh_display_locally.assert_called()
        else:
            pytest.fail("GraphWidget missing _on_lexicon_preview_requested slot")

    def test_graph_widget_reverts_on_cancel(self, qapp):
        """Verify GraphWidget reverts lexicon if dialog is rejected."""
        graph = GraphWidget()

        # Initial state
        original_lexicon = {"nodes": {"hero": {"color": "#000000"}}, "edges": {}}
        graph._raw_lexicon = original_lexicon
        graph._resolved_lexicon = original_lexicon

        # Mock dependencies
        graph._refresh_display_locally = MagicMock()

        # Mock the dialog execution
        with patch(
            "src.gui.dialogs.lexicon_editor_dialog.LexiconEditorDialog"
        ) as MockDialog:
            instance = MockDialog.return_value
            instance.exec.return_value = QDialog.DialogCode.Rejected
            instance.get_lexicon_config.return_value = {
                "nodes": {}
            }  # Changed but rejected

            # Run the show method
            graph.show_lexicon_editor()

            # Verify persisted state is ORIGINAL, not empty
            assert graph._raw_lexicon == original_lexicon
