"""Prompt Syntax Highlighter Module.

Provides syntax highlighting for prompt template variables in braces.
"""

import re

from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


class PromptSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for prompt variables in braces {variable}."""

    def __init__(self, parent: QTextDocument) -> None:
        """Initialize the syntax highlighter.

        Args:
            parent: The QTextDocument to highlight.
        """
        super().__init__(parent)
        self._highlighting_rules = []

        # Define the format for variables
        variable_format = QTextCharFormat()
        variable_format.setForeground(QColor("#FF8C00"))  # Dark Orange for standout
        variable_format.setFontWeight(QFont.Weight.Bold)

        # Simple rule: anything inside { }
        # We use a lazy match to capture {var} without eating too much
        self._highlighting_rules.append((re.compile(r"\{[^}]*\}"), variable_format))

    def highlightBlock(self, text: str) -> None:
        """Apply highlighting to the given block of text."""
        for pattern, format in self._highlighting_rules:
            iterator = pattern.finditer(text)
            for match in iterator:
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)
