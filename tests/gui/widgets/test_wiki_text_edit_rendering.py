import unittest
from PySide6.QtWidgets import QApplication
from src.gui.widgets.wiki_text_edit import WikiTextEdit

# Ensure QApplication exists
app = QApplication.instance() or QApplication([])


class TestWikiTextEditRendering(unittest.TestCase):
    def setUp(self):
        self.editor = WikiTextEdit()
        # Mock completion map with one known item
        # items format: list of (id, name, type)
        items = [("id-123", "Known Entity", "entity")]
        self.editor.set_completer(items=items)

    def test_rendering_known_entity(self):
        """Test that known entities are rendered as standard links."""
        text = "[[Known Entity]]"
        self.editor.set_wiki_text(text)
        html = self.editor.toHtml()

        # Should contain a link to Known Entity
        self.assertIn('href="Known Entity"', html)
        # Should NOT contain red color style
        self.assertNotIn("color: red", html)

    def test_rendering_unknown_entity(self):
        """Test that unknown entities are rendered with red color."""
        text = "[[Unknown Ghost]]"
        self.editor.set_wiki_text(text)
        html = self.editor.toHtml()

        # Should contain a link to Unknown Ghost
        self.assertIn('href="Unknown Ghost"', html)
        # Should contain inline style for red color
        # Note: HTML serialization might vary, checking key parts
        self.assertIn("color:#ff0000", html)

    def test_rendering_mixed(self):
        """Test mixed known and unknown entities."""
        text = "[[Known Entity]] and [[Unknown Ghost]]"
        self.editor.set_wiki_text(text)
        html = self.editor.toHtml()

        self.assertIn('href="Known Entity"', html)
        self.assertIn('href="Unknown Ghost"', html)

        # We need to be careful with assertIn here as toHtml dumps the whole doc
        # But we can check that at least one instance of red is there
        self.assertIn("color:#ff0000", html)

    def test_rendering_case_insensitive(self):
        """Test that casing differences are ignored."""
        text = "[[known entity]]"  # lower case vs "Known Entity" in map
        self.editor.set_wiki_text(text)
        html = self.editor.toHtml()

        # Should be valid (no red)
        self.assertNotIn("color:#ff0000", html)
        self.assertIn('href="known entity"', html)

    def test_rendering_id_based_link(self):
        """Test that ID-based links with 'id:' prefix are validated correctly."""
        # Link format: [[id:UUID|Label]] where UUID matches "id-123" in items
        text = "[[id:id-123|Known Entity]]"
        self.editor.set_wiki_text(text)
        html = self.editor.toHtml()

        # Should be valid (no red) because "id-123" is in _valid_ids
        self.assertNotIn("color:#ff0000", html)
        self.assertIn('href="id:id-123"', html)


if __name__ == "__main__":
    unittest.main()
