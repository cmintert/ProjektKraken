"""
Generation Review Dialog.

Modal dialog for reviewing and editing LLM-generated content before
applying it to the description field.
"""

import logging
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class ReviewAction(Enum):
    """Actions available in the review dialog."""

    REPLACE = auto()
    APPEND = auto()
    DISCARD = auto()


class GenerationReviewDialog(QDialog):
    """
    Dialog for reviewing LLM-generated content before applying.

    Provides editable preview, rating buttons, and action choices
    (replace, append, or discard).
    """

    def __init__(
        self,
        generated_text: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the generation review dialog.

        Args:
            generated_text: The LLM-generated text to review.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Review Generated Content")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)

        # State
        self.action: Optional[ReviewAction] = None
        self.rating: Optional[int] = None  # 1 = thumbs up, -1 = thumbs down

        self._setup_ui(generated_text)

    def _setup_ui(self, generated_text: str) -> None:
        """
        Set up the dialog UI.

        Args:
            generated_text: Initial text to display in editor.
        """
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # Apply dark theme
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        # Header label
        header = QLabel("Review and edit the generated content before applying:")
        header.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        main_layout.addWidget(header)

        # Editable text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(generated_text)
        self.text_edit.setStyleSheet(StyleHelper.get_input_field_style())
        main_layout.addWidget(self.text_edit, stretch=1)

        # Rating section
        rating_layout = QHBoxLayout()
        rating_label = QLabel("Rate this result:")
        rating_label.setStyleSheet("color: #888888;")
        rating_layout.addWidget(rating_label)

        self.thumbs_up_btn = QPushButton("👍")
        self.thumbs_up_btn.setFixedWidth(50)
        self.thumbs_up_btn.setToolTip("Good result")
        self.thumbs_up_btn.setCheckable(True)
        self.thumbs_up_btn.clicked.connect(self._on_thumbs_up_clicked)
        rating_layout.addWidget(self.thumbs_up_btn)

        self.thumbs_down_btn = QPushButton("👎")
        self.thumbs_down_btn.setFixedWidth(50)
        self.thumbs_down_btn.setToolTip("Poor result")
        self.thumbs_down_btn.setCheckable(True)
        self.thumbs_down_btn.clicked.connect(self._on_thumbs_down_clicked)
        rating_layout.addWidget(self.thumbs_down_btn)

        rating_layout.addStretch()
        main_layout.addLayout(rating_layout)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        # Discard button (left)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setToolTip("Discard generated content")
        self.discard_btn.setStyleSheet("color: #e74c3c;")
        self.discard_btn.clicked.connect(self._on_discard_clicked)
        buttons_layout.addWidget(self.discard_btn)

        # Append button
        self.append_btn = QPushButton("Append")
        self.append_btn.setToolTip("Append to existing description")
        self.append_btn.clicked.connect(self._on_append_clicked)
        buttons_layout.addWidget(self.append_btn)

        # Replace button (primary action)
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.setToolTip("Replace existing description")
        self.replace_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        self.replace_btn.clicked.connect(self._on_replace_clicked)
        buttons_layout.addWidget(self.replace_btn)

        main_layout.addLayout(buttons_layout)

    def get_text(self) -> str:
        """
        Get the current text from the editor.

        Returns:
            str: The text in the editor (possibly edited by user).
        """
        return self.text_edit.toPlainText()

    def get_result(self) -> dict:
        """
        Get the dialog result including action, text, and rating.

        Returns:
            dict: Result with 'action', 'text', and 'rating' keys.
        """
        return {
            "action": self.action,
            "text": self.get_text(),
            "rating": self.rating,
        }

    @Slot()
    def _on_thumbs_up_clicked(self) -> None:
        """Handle thumbs up button click."""
        self.rating = 1
        self.thumbs_up_btn.setChecked(True)
        self.thumbs_down_btn.setChecked(False)
        logger.debug("User rated generation: thumbs up")

    @Slot()
    def _on_thumbs_down_clicked(self) -> None:
        """Handle thumbs down button click."""
        self.rating = -1
        self.thumbs_down_btn.setChecked(True)
        self.thumbs_up_btn.setChecked(False)
        logger.debug("User rated generation: thumbs down")

    @Slot()
    def _on_replace_clicked(self) -> None:
        """Handle Replace button click."""
        self.action = ReviewAction.REPLACE
        logger.info("User chose to replace description with generated content")
        self.accept()

    @Slot()
    def _on_append_clicked(self) -> None:
        """Handle Append button click."""
        self.action = ReviewAction.APPEND
        logger.info("User chose to append generated content to description")
        self.accept()

    @Slot()
    def _on_discard_clicked(self) -> None:
        """Handle Discard button click."""
        self.action = ReviewAction.DISCARD
        logger.info("User discarded generated content")
        self.reject()
