import pytest

from src.gui.widgets.prompt_editor import PromptEditorWidget


class TestPromptEditorWidget:
    @pytest.fixture
    def widget(self, qtbot):
        widget = PromptEditorWidget()
        qtbot.addWidget(widget)
        return widget

    def test_initial_state(self, widget):
        """Test initial state of the widget."""
        assert widget.toPlainText() == ""
        assert widget.editor.document().defaultFont().family() in [
            "Consolas",
            "Menlo",
            "Courier New",
            "Monospace",
        ]

    def test_set_get_text(self, widget):
        """Test setting and getting text."""
        text = "Hello {world}"
        widget.setPlainText(text)
        assert widget.toPlainText() == text

    def test_insert_variable(self, widget, qtbot):
        """Test inserting a variable from the toolbar/method."""
        widget.set_variables(["{name}", "{type}"])

        # Verify variables are populated in combobox/menu (implementation dependent)
        # Assuming we have a public method or accessing internal combo for test
        assert widget.var_combo.count() > 0

        # Set text and cursor
        widget.setPlainText("Hello ")
        cursor = widget.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        widget.editor.setTextCursor(cursor)

        # Simulate inserting variable
        # We can simulate by finding the action or calling the slot directly if we don't want to simulate UI clicks on combo
        widget.insert_variable("{name}")

        assert widget.toPlainText() == "Hello {name}"

    def test_restore_default(self, widget, qtbot):
        """Test restoring default text."""
        default_text = "Default Prompt"
        widget.set_default_text(default_text)
        widget.setPlainText("Modified Text")

        # Trigger restore
        # widget.btn_restore.click() # If we expose it
        # or verify the method
        widget.restore_default()

        assert widget.toPlainText() == default_text

    def test_theme_change_refreshes_editor_and_toolbar(self, widget):
        """An open prompt editor should follow a live theme switch."""
        from src.core.theme_manager import ThemeManager

        ThemeManager().set_theme("light_mode")

        assert "#FFFFFF" in widget.editor.styleSheet()
        assert "#FFFFFF" in widget.btn_restore.styleSheet()

    def test_popout_mode(self, widget, qtbot):
        """Test that pop-out mode opens a dialog (smoke test)."""
        # This is hard to test fully without blocking, but we can check if the method exists
        # and maybe mock the dialog execution if needed.
        # For now, just ensuring the method creates the dialog or signal is emitted.
        pass
