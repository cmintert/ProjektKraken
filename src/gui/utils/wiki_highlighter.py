"""
Wiki Syntax Highlighter.
Highlights [[WikiLinks]] in a QTextDocument.
"""

import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt


class WikiSyntaxHighlighter(QSyntaxHighlighter):
    """
    Highlighter for WikiLinks in the format [[target]].
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setForeground(QColor("#4da6ff"))  # Light blue
        self.highlight_format.setFontWeight(QFont.Bold)
        self.highlight_format.setUnderlineStyle(QTextCharFormat.SingleUnderline)

        # Pattern: [[ followed by anything lazy until ]]
        self.pattern = re.compile(r"\[\[(.*?)\]\]")

    def highlightBlock(self, text):
        """
        Applies highlighting to the given block of text.
        """
        for match in self.pattern.finditer(text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.highlight_format)
