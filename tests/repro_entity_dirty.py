import sys
import logging
from PySide6.QtWidgets import QApplication, QWidget
from unittest.mock import MagicMock, patch
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.core.entities import Entity

# Configure logging
logging.basicConfig(level=logging.DEBUG)


class StubMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = MagicMock()


class StubGalleryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_owner = MagicMock()


def repro():
    app = QApplication(sys.argv)

    stub_parent = StubMainWindow()

    with patch("src.gui.widgets.gallery_widget.GalleryWidget", StubGalleryWidget):
        editor = EntityEditorWidget(parent=stub_parent)
        editor.show()

        # Create dummy entity
        entity = Entity(
            name="Test Entity",
            type="Person",
            description="Test description",
            attributes={"Key": "Value", "_tags": ["tag1", "tag2"]},
        )

        print("Loading entity...")
        editor.load_entity(entity)

        print(f"Is Dirty after load? {editor.has_unsaved_changes()}")

        if editor.has_unsaved_changes():
            print("FAIL: EntityEditor is dirty immediately after load.")
        else:
            print("PASS: EntityEditor is clean after load.")

        # Iterate a few main loop events
        app.processEvents()

        print(f"Is Dirty after processEvents? {editor.has_unsaved_changes()}")

        editor.close()


if __name__ == "__main__":
    repro()
