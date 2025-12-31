import sys
import logging
from PySide6.QtWidgets import QApplication, QWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.core.events import Event

# Configure logging to see my instrumentation
logging.basicConfig(level=logging.DEBUG)


from unittest.mock import MagicMock, patch


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
        editor = EventEditorWidget(parent=stub_parent)
        editor.show()

        # Create dummy event
        event = Event(
            name="Test Event",
            lore_date=100.0,
            lore_duration=10.0,
            type="generic",
            description="Test description with [[WikiLink]]",
            attributes={"Key": "Value", "_tags": ["tag1", "tag2"]},
        )

        print("Loading event...")
        editor.load_event(event)

        print(f"Is Dirty after load? {editor.has_unsaved_changes()}")

        if editor.has_unsaved_changes():
            print("FAIL: Editor is dirty immediately after load.")
        else:
            print("PASS: Editor is clean after load.")

        # Iterate a few main loop events to see if delayed signals fire
        app.processEvents()

        print(f"Is Dirty after processEvents? {editor.has_unsaved_changes()}")

        # Clean up
        editor.close()


if __name__ == "__main__":
    repro()
