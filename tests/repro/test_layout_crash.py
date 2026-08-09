from src.gui.widgets.tag_editor import TagEditorWidget


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
