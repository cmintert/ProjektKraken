"""Tests for the Lexicon Editor clear-icon behaviour.

Validates that the Clear Icon button correctly resets icon_path,
updates the button labels, and reverts the shape combo.
"""

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.lexicon_editor_dialog import LexiconEditorDialog


@pytest.fixture
def qapp():
    """Provides a QApplication instance for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Clear icon button existence
# ---------------------------------------------------------------------------


class TestClearIconButtonExists:
    """Tests for Clear Icon button presence in node rows."""

    def test_clear_button_present(self, qapp):
        """Each entity-type row has a clear_btn widget."""
        dialog = LexiconEditorDialog(entity_types=["deity", "hero"])
        for etype in ["deity", "hero"]:
            assert "clear_btn" in dialog._node_rows[etype]

    def test_clear_button_disabled_when_no_icon(self, qapp):
        """Clear button is disabled when there is no icon set."""
        dialog = LexiconEditorDialog(entity_types=["deity"])
        assert not dialog._node_rows["deity"]["clear_btn"].isEnabled()

    def test_clear_button_enabled_when_icon_set(self, qapp):
        """Clear button is enabled when an icon is already configured."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        assert dialog._node_rows["deity"]["clear_btn"].isEnabled()


# ---------------------------------------------------------------------------
# Clear icon behaviour
# ---------------------------------------------------------------------------


class TestClearIconBehaviour:
    """Tests for _clear_icon method behaviour."""

    def test_clears_icon_path(self, qapp):
        """_clear_icon sets icon_path to empty string."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        assert dialog._node_rows["deity"]["icon_path"] == ""

    def test_resets_button_text(self, qapp):
        """After clear, the icon button shows 'Import' text."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        assert "Import" in dialog._node_rows["deity"]["icon_btn"].text()

    def test_disables_clear_button(self, qapp):
        """After clear, the clear button is disabled."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        assert not dialog._node_rows["deity"]["clear_btn"].isEnabled()

    def test_reverts_shape_from_image(self, qapp):
        """When shape is 'image', clearing icon resets it to 'dot'."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        assert dialog._node_rows["deity"]["shape"].currentText() == "dot"

    def test_preserves_non_image_shape(self, qapp):
        """When shape is not 'image', clearing icon preserves it."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "star",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        assert dialog._node_rows["deity"]["shape"].currentText() == "star"

    def test_config_readback_has_no_icon(self, qapp):
        """After clearing, get_lexicon_config should not have icon key."""
        config = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"], current_config=config
        )
        dialog._clear_icon("deity")
        result = dialog.get_lexicon_config()
        assert "icon" not in result["nodes"]["deity"]

    def test_noop_for_unknown_type(self, qapp):
        """_clear_icon is a no-op for a type that doesn't exist."""
        dialog = LexiconEditorDialog(entity_types=["deity"])
        # Should not raise
        dialog._clear_icon("nonexistent")
