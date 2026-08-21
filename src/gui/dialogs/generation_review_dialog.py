"""Generation Review Dialog.

Modal dialog for reviewing and editing LLM-generated content before applying it to the
description field.
"""

import logging
from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_generation import (
    GenerationApplyMode,
    GenerationReviewResult,
    ModelReply,
)
from src.core.description_date_policy import find_description_dates
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

_DATE_WARNING_EXCERPT_LIMIT = 3


# Backwards-compatible import for callers and existing extensions.
ReviewAction = GenerationApplyMode


class GenerationReviewDialog(QDialog):
    """Dialog for reviewing LLM-generated content before applying.

    Provides editable preview, rating buttons, and action choices (replace, append, or
    discard).
    """

    def __init__(
        self,
        generated_text: str,
        parent: Optional[QWidget] = None,
        reply: ModelReply | None = None,
        month_names: tuple[str, ...] = (),
        era_names: tuple[str, ...] = (),
        known_date_values: tuple[float, ...] = (),
    ) -> None:
        """Initialize the generation review dialog.

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
        self.reply = reply
        self._month_names = month_names
        self._era_names = era_names
        self._known_date_values = known_date_values
        self.action: Optional[GenerationApplyMode] = None
        self.rating: Optional[int] = None  # 1 = thumbs up, -1 = thumbs down
        self.comment: Optional[str] = None

        self._setup_ui(generated_text)

    def _setup_ui(self, generated_text: str) -> None:
        """Set up the dialog UI.

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

        if self.reply is not None:
            details = []
            if self.reply.model:
                details.append(self.reply.model)
            if self.reply.finish_reason:
                details.append(f"finish: {self.reply.finish_reason}")
            if details:
                reply_details = QLabel(" · ".join(details))
                reply_details.setStyleSheet(
                    f"color: {StyleHelper.get_dim_text_color()};"
                )
                main_layout.addWidget(reply_details)
            if self.reply.finish_reason == "length":
                truncation_warning = QLabel(
                    "The model stopped at the token limit; this reply may be truncated."
                )
                truncation_warning.setWordWrap(True)
                truncation_warning.setStyleSheet(
                    StyleHelper.get_error_label_style()
                )
                main_layout.addWidget(truncation_warning)

        # Editable text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(generated_text)
        self.text_edit.setStyleSheet(StyleHelper.get_input_field_style())
        main_layout.addWidget(self.text_edit, stretch=1)

        self.date_warning = QLabel()
        self.date_warning.setWordWrap(True)
        self.date_warning.setStyleSheet(StyleHelper.get_error_label_style())
        self.date_warning.hide()
        main_layout.addWidget(self.date_warning)

        # Rating section
        rating_layout = QHBoxLayout()
        rating_label = QLabel("Rate this result:")
        rating_label.setStyleSheet(
            f"color: {StyleHelper.get_dim_text_color()};"
        )
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

        # Comment field
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText("Optional comment…")
        self.comment_edit.setMaxLength(200)
        self.comment_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.comment_edit.textChanged.connect(self._on_comment_changed)
        main_layout.addWidget(self.comment_edit)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        # Discard button (left)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setToolTip("Discard generated content")
        self.discard_btn.setStyleSheet(
            StyleHelper.get_ghost_destructive_button_style()
        )
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
        self.text_edit.textChanged.connect(self._validate_date_policy)
        self._validate_date_policy()

    @Slot()
    def _validate_date_policy(self) -> bool:
        """Update apply controls from the generated-description date rule."""
        violations = find_description_dates(
            self.text_edit.toPlainText(),
            month_names=self._month_names,
            era_names=self._era_names,
            known_date_values=self._known_date_values,
        )
        valid = not violations
        self.append_btn.setEnabled(valid)
        self.replace_btn.setEnabled(valid)
        if valid:
            self.date_warning.clear()
            self.date_warning.hide()
        else:
            excerpts = ", ".join(
                f'“{item.text}”'
                for item in violations[:_DATE_WARNING_EXCERPT_LIMIT]
            )
            suffix = (
                "…" if len(violations) > _DATE_WARNING_EXCERPT_LIMIT else ""
            )
            self.date_warning.setText(
                "Descriptions cannot contain explicit dates. Remove "
                f"{excerpts}{suffix} before applying."
            )
            self.date_warning.show()
        return valid

    def get_text(self) -> str:
        """Get the current text from the editor.

        Returns:
            str: The text in the editor (possibly edited by user).

        """
        return self.text_edit.toPlainText()

    def get_result(self) -> dict:
        """Get the dialog result including action, text, and rating.

        Returns:
            dict: Result with 'action', 'text', and 'rating' keys.

        """
        return {
            "action": self.action,
            "text": self.get_text(),
            "rating": self.rating,
            "comment": self.comment,
        }

    def get_review_result(self) -> GenerationReviewResult:
        """Return the typed result consumed by description editors."""
        return GenerationReviewResult(
            action=self.action or GenerationApplyMode.DISCARD,
            text=self.get_text(),
            rating=self.rating or 0,
            comment=self.comment or "",
            reply=self.reply,
        )

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

    @Slot(str)
    def _on_comment_changed(self, text: str) -> None:
        """Handle comment field text change."""
        self.comment = text.strip() or None

    @Slot()
    def _on_replace_clicked(self) -> None:
        """Handle Replace button click."""
        if not self._validate_date_policy():
            return
        self.action = GenerationApplyMode.REPLACE
        logger.info("User chose to replace description with generated content")
        self.accept()

    @Slot()
    def _on_append_clicked(self) -> None:
        """Handle Append button click."""
        if not self._validate_date_policy():
            return
        self.action = GenerationApplyMode.APPEND
        logger.info("User chose to append generated content to description")
        self.accept()

    @Slot()
    def _on_discard_clicked(self) -> None:
        """Handle Discard button click."""
        self.action = GenerationApplyMode.DISCARD
        logger.info("User discarded generated content")
        self.reject()
