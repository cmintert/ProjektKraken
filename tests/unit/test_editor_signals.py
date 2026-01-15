from src.gui.widgets.wiki_text_edit import WikiTextEdit


def test_formatting_triggers_text_changed_signal(qtbot):
    """Test that applying formatting (Bold, Heading) triggers textChanged signal."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text("Hello World")

    # Track signal
    with qtbot.waitSignal(widget.textChanged, timeout=1000, raising=True):
        # Apply Bold
        widget._set_heading(1)


def test_text_modification_triggers_text_changed_signal(qtbot):
    """Test that standard typing triggers textChanged signal."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text("Hello World")

    with qtbot.waitSignal(widget.textChanged, timeout=1000):
        widget.insertPlainText("!")
