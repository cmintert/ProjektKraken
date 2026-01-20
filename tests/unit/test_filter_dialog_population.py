import pytest
from PySide6.QtCore import Qt
from src.gui.dialogs.filter_dialog import FilterDialog
from src.gui.widgets.filter_widget import FilterWidget


class TestFilterDialogPopulation:
    def test_dialog_populates_tags(self, qtbot):
        """Test that FilterDialog correctly populates tags in FilterWidget."""
        tags = ["TagA", "TagB", "TagC"]
        dialog = FilterDialog(available_tags=tags)
        qtbot.addWidget(dialog)

        # Access inner widget
        filter_widget = dialog.filter_widget

        # Check explicit items list
        assert filter_widget.items == ["TagA", "TagB", "TagC"]

        # Check UI list items
        list_include = filter_widget.list_include
        assert list_include.count() == 3
        items = [list_include.item(i).text() for i in range(list_include.count())]
        assert sorted(items) == sorted(tags)
