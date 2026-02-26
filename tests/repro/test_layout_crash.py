from PySide6.QtWidgets import QPushButton, QWidget

from src.gui.widgets.flow_layout import FlowLayout
from src.gui.widgets.tag_editor import TagEditorWidget


def test_flow_layout_no_zombie_errors(qtbot, capsys):
    """Confirm the 'Internal C++ object already deleted' error does NOT appear."""
    parent = QWidget()
    layout = FlowLayout(parent)
    qtbot.addWidget(parent)

    btn = QPushButton("Stale")
    layout.addWidget(btn)

    # Process events
    qtbot.wait(10)

    # Remove button and calculate layout
    layout.takeAt(0)
    btn.deleteLater()
    qtbot.wait(10)

    layout.heightForWidth(100)

    # Check stderr for the error message - should be empty/no crash
    captured = capsys.readouterr()
    assert "Internal C++ object" not in captured.err


def test_tag_editor_load_tags_no_noise(qtbot, capsys):
    """Check for no stderr noise during rapid tag loading."""
    editor = TagEditorWidget()
    qtbot.addWidget(editor)
    editor.show()

    for i in range(10):
        editor.load_tags([f"tag_{i}_{j}" for j in range(3)])

    qtbot.wait(10)
    captured = capsys.readouterr()
    assert "Internal C++ object" not in captured.err
