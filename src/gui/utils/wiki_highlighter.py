"""
Wiki Syntax Highlighter.
Highlights [[WikiLinks]] in a QTextDocument with different styles for
valid and broken ID-based links.
"""

import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from typing import Optional


class WikiSyntaxHighlighter(QSyntaxHighlighter):
    """
    Highlighter for WikiLinks in the format [[target]] or [[id:UUID|Label]].
    
    Supports different visual styles for:
    - Regular links (name-based or valid ID-based)
    - Broken links (ID-based links where target doesn't exist)
    """

    def __init__(self, parent=None, link_resolver=None):
        """
        Initializes the WikiSyntaxHighlighter.

        Args:
            parent (QTextDocument, optional): The parent text document. Defaults to None.
            link_resolver: Optional LinkResolver to check for broken links.
        """
        super().__init__(parent)
        
        # Format for valid links
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setForeground(QColor("#4da6ff"))  # Light blue
        self.highlight_format.setFontWeight(QFont.Bold)
        self.highlight_format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        
        # Format for broken links
        self.broken_format = QTextCharFormat()
        self.broken_format.setForeground(QColor("#ff6b6b"))  # Red
        self.broken_format.setFontWeight(QFont.Bold)
        self.broken_format.setFontStrikeOut(True)

        # Pattern: [[ followed by anything lazy until ]]
        self.pattern = re.compile(r"\[\[(.*?)\]\]")
        self.id_pattern = re.compile(r"^id:([a-f0-9-]{36})", re.IGNORECASE)
        
        self.link_resolver = link_resolver

    def set_link_resolver(self, link_resolver):
        """
        Sets the link resolver for checking broken links.
        
        Args:
            link_resolver: LinkResolver instance.
        """
        self.link_resolver = link_resolver
        self.rehighlight()

    def highlightBlock(self, text):
        """
        Applies highlighting to the given block of text.
        
        Uses different styles for valid vs broken links.
        """
        for match in self.pattern.finditer(text):
            start = match.start()
            length = match.end() - start
            content = match.group(1)
            
            # Determine if this is a broken link
            is_broken = False
            if self.link_resolver:
                # Check if ID-based link
                id_match = self.id_pattern.match(content)
                if id_match:
                    target_id = id_match.group(1)
                    # Check if link is broken
                    if self.link_resolver.resolve(target_id) is None:
                        is_broken = True
            
            # Apply appropriate format
            if is_broken:
                self.setFormat(start, length, self.broken_format)
            else:
                self.setFormat(start, length, self.highlight_format)
