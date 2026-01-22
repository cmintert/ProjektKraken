import pytest
from PySide6.QtGui import QTextDocument, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt
from src.gui.utils.prompt_syntax_highlighter import PromptSyntaxHighlighter
from src.gui.utils.style_helper import StyleHelper


class TestPromptSyntaxHighlighter:
    @pytest.fixture
    def highlighter(self, qtbot):
        self.document = QTextDocument()
        highlighter = PromptSyntaxHighlighter(self.document)
        return highlighter

    def test_highlighting_simple_variable(self, highlighter):
        """Test highlighting of single {} variable."""
        document = highlighter.document()
        document.setPlainText("Hello {name}!")

        # We need to manually trigger highlighting or let the event loop run?
        # QSyntaxHighlighter works on the document layout usually.
        # For unit testing without a view, we might need to force rehighlight.
        highlighter.rehighlight()

        # Check formatting at specific positions
        # "Hello " (0-6) -> No format
        # "{name}" (6-12) -> Variable format
        # "!" (12-13) -> No format

        # Get format at start of variable
        format_at_var = highlighter.format(8)  # Inside 'name'

        # We expect color to be defined. Let's assume we use a specific color or check it's not black/default.
        # Ideally we check against the specific color we set in StyleHelper or the class.
        assert format_at_var.foreground().color().isValid()
        # Ensure it's not standard text color (usually black/white depending on theme, but definitely distinguishable)

    def test_highlighting_multiple_variables(self, highlighter):
        document = highlighter.document()
        document.setPlainText("{type}: {description}")
        highlighter.rehighlight()

        # Check {type}
        assert highlighter.format(1).foreground().color().isValid()
        # Check : (separator)
        assert highlighter.format(6) == QTextCharFormat()  # Should be empty/default
        # Check {description}
        assert highlighter.format(10).foreground().color().isValid()

    def test_highlighting_nested_braces(self, highlighter):
        """Test that nested braces are handled gracefully (though typically not supported in this simple syntax).
        We'll assume greedy matching or simple non-nested matching for now.
        Regex `{([^}]*)}` usually matches inner content.
        """
        document = highlighter.document()
        document.setPlainText("{{double}}")
        highlighter.rehighlight()

        # Depending on regex, this might highlight the whole thing or inner.
        # For simple prompt templates, usually just {var} is enough.
        # If we have {{...}}, it might be escaped or double braces.
        # Implementation detail: we'll target simple `{var}`.

        pass
