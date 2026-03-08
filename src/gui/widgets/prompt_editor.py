"""Prompt Editor Widget Module.

Provides a widget for editing AI prompts with syntax highlighting and variable insertion.
"""

from typing import List, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.prompt_syntax_highlighter import PromptSyntaxHighlighter
from src.gui.utils.style_helper import StyleHelper


class PromptEditorWidget(QWidget):
    """Widget for editing prompts with syntax highlighting and variable insertion."""

    textChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the prompt editor widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._default_text = ""
        self._highlighting_rules = []

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        # Variable insertion
        self.var_combo = QComboBox()
        self.var_combo.setPlaceholderText("Insert Variable...")
        self.var_combo.setMinimumWidth(150)
        self.var_combo.activated.connect(self._on_variable_selected)
        toolbar_layout.addWidget(self.var_combo)

        toolbar_layout.addStretch()

        # Restore default button
        self.btn_restore = QToolButton()
        self.btn_restore.setText(
            "Restore Default"
        )  # Icon would be better but text for now
        self.btn_restore.setToolTip("Restore default prompt")
        self.btn_restore.setStyleSheet(StyleHelper.get_tool_button_style())
        self.btn_restore.clicked.connect(self.restore_default)
        toolbar_layout.addWidget(self.btn_restore)

        # Pop-out button
        self.btn_popout = QToolButton()
        self.btn_popout.setText("⤢")  # Unicode expand symbol
        self.btn_popout.setToolTip("Open in larger editor")
        self.btn_popout.setStyleSheet(StyleHelper.get_tool_button_style())
        self.btn_popout.clicked.connect(self._open_popout)
        toolbar_layout.addWidget(self.btn_popout)

        layout.addLayout(toolbar_layout)

        # Editor
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Enter prompt here...")

        # Set monospace font
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Menlo")
            if not font.exactMatch():
                font = QFont("Courier New")
        self.editor.setStyleSheet(StyleHelper.get_input_field_style())
        self.editor.setFont(font)

        self.editor.textChanged.connect(self.textChanged)
        layout.addWidget(self.editor)

        # Syntax Highlighter
        self.highlighter = PromptSyntaxHighlighter(self.editor.document())

    def setPlainText(self, text: str) -> None:
        """Set the editor text content.

        Args:
            text: Text to set in the editor.
        """
        self.editor.setPlainText(text)

    def setPlaceholderText(self, text: str) -> None:
        """Set the editor placeholder text.

        Args:
            text: Placeholder text to display when editor is empty.
        """
        self.editor.setPlaceholderText(text)

    def toPlainText(self) -> str:
        """Get the current editor text content.

        Returns:
            The current text in the editor.
        """
        return self.editor.toPlainText()

    def clear(self) -> None:
        """Clear the editor content."""
        self.editor.clear()

    def set_variables(self, variables: List[str]) -> None:
        """Set the list of available variables.

        Hides the combo box if no variables are provided.
        """
        self.var_combo.clear()
        if not variables:
            self.var_combo.hide()
            return

        self.var_combo.addItem("Insert Variable...", None)  # Header
        for var in variables:
            self.var_combo.addItem(var, var)
        self.var_combo.show()

    def set_default_text(self, text: str) -> None:
        """Set the default prompt text for restoration.

        Args:
            text: Default text to restore to when restore_default is called.
        """
        self._default_text = text

    def insert_variable(self, variable: str) -> None:
        """Insert a variable at the current cursor position.

        Args:
            variable: Variable text to insert.
        """
        self.editor.insertPlainText(variable)
        self.editor.setFocus()

    @Slot(int)
    def _on_variable_selected(self, index: int) -> None:
        """Handle variable selection from dropdown.

        Args:
            index: Index of selected variable in combo box.
        """
        if index <= 0:
            return

        variable = self.var_combo.itemData(index)
        if variable:
            self.insert_variable(variable)
            self.var_combo.setCurrentIndex(0)  # Reset to header

    @Slot()
    def restore_default(self) -> None:
        """Restore the editor to the default prompt text."""
        if self._default_text:
            self.editor.setPlainText(self._default_text)

    @Slot()
    def _open_popout(self) -> None:
        """Open a modal dialog with a larger editor."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Prompt")
        dialog.resize(800, 600)

        dialog.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(dialog)
        StyleHelper.apply_compact_spacing(layout)

        # Use another instance of PromptEditorWidget or just a big text edit?
        # Better to replicate the editing experience.
        # For simplicity, we'll just move the content to a big text edit here,
        # but realistically we want the same features.
        # Let's create a temporary editor widget inside the dialog.

        pop_editor = QPlainTextEdit()
        pop_editor.setFont(self.editor.font())
        pop_editor.setPlainText(self.toPlainText())
        pop_editor.setStyleSheet(StyleHelper.get_input_field_style())

        # Attach highlighter to popout too
        _ = PromptSyntaxHighlighter(pop_editor.document())  # Keep ref

        layout.addWidget(pop_editor)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        # Use Standard/Destructive or ToolButton style?
        # Standard buttons don't have a helper yet besides Primary/Destructive class usage.
        # We can reuse get_tool_button_style or just leave native?
        # User complained about "modal does not adhere to styles".
        # Let's use get_tool_button_style for Cancel (secondary)
        btn_cancel.setStyleSheet(StyleHelper.get_tool_button_style())
        btn_box.addWidget(btn_cancel)

        btn_ok = QPushButton("Apply")
        btn_ok.clicked.connect(dialog.accept)
        # Use Primary Button Style
        btn_ok.setStyleSheet(StyleHelper.get_primary_button_style())
        btn_box.addWidget(btn_ok)

        layout.addLayout(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setPlainText(pop_editor.toPlainText())
