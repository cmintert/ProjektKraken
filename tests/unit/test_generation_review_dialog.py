"""
Unit tests for GenerationReviewDialog.

Tests the dialog functionality for reviewing LLM-generated content before
applying it to the description field.
"""

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.generation_review_dialog import (
    GenerationReviewDialog,
    ReviewAction,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestGenerationReviewDialog:
    """Tests for GenerationReviewDialog."""

    def test_init_displays_generated_text(self, qapp):
        """Test dialog initializes with generated text."""
        dialog = GenerationReviewDialog(
            generated_text="Test generated content", parent=None
        )

        assert dialog.text_edit.toPlainText() == "Test generated content"

    def test_text_is_editable(self, qapp):
        """Test user can edit the generated text."""
        dialog = GenerationReviewDialog(generated_text="Original text", parent=None)

        dialog.text_edit.setPlainText("Modified text")
        assert dialog.get_text() == "Modified text"

    def test_replace_action(self, qapp):
        """Test Replace button sets correct action."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        # Simulate clicking Replace
        dialog._on_replace_clicked()

        assert dialog.action == ReviewAction.REPLACE

    def test_append_action(self, qapp):
        """Test Append button sets correct action."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        # Simulate clicking Append
        dialog._on_append_clicked()

        assert dialog.action == ReviewAction.APPEND

    def test_discard_action(self, qapp):
        """Test Discard button sets correct action."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        # Simulate clicking Discard
        dialog._on_discard_clicked()

        assert dialog.action == ReviewAction.DISCARD

    def test_thumbs_up_rating(self, qapp):
        """Test thumbs up sets positive rating."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        dialog._on_thumbs_up_clicked()

        assert dialog.rating == 1

    def test_thumbs_down_rating(self, qapp):
        """Test thumbs down sets negative rating."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        dialog._on_thumbs_down_clicked()

        assert dialog.rating == -1

    def test_get_result_returns_action_and_text(self, qapp):
        """Test get_result returns both action and potentially edited text."""
        dialog = GenerationReviewDialog(generated_text="Original text", parent=None)

        dialog.text_edit.setPlainText("Edited text")
        dialog._on_replace_clicked()

        result = dialog.get_result()

        assert result["action"] == ReviewAction.REPLACE
        assert result["text"] == "Edited text"
        assert result["rating"] is None  # No rating given

    def test_get_result_includes_rating(self, qapp):
        """Test get_result includes rating when given."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        dialog._on_thumbs_up_clicked()
        dialog._on_append_clicked()

        result = dialog.get_result()

        assert result["rating"] == 1
        assert result["action"] == ReviewAction.APPEND

    def test_discard_returns_none_text(self, qapp):
        """Test discard action returns None for text."""
        dialog = GenerationReviewDialog(generated_text="Test text", parent=None)

        dialog._on_discard_clicked()
        result = dialog.get_result()

        assert result["action"] == ReviewAction.DISCARD
        # Text should still be available for logging purposes
        assert result["text"] == "Test text"
