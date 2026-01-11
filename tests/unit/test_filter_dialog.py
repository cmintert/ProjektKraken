import pytest
from PySide6.QtCore import Qt

# We need to import the class, but it doesn't exist yet, so this test will fail import.
# Using try-except import or just letting it fail is standard Red phase.
try:
    from src.gui.dialogs.filter_dialog import FilterDialog
except ImportError:
    FilterDialog = None


@pytest.mark.unit
class TestFilterDialog:
    """Tests for the Advanced Filter Dialog."""

    @pytest.fixture
    def dialog(self, qapp):
        """Creates the dialog with some sample tags."""
        if FilterDialog is None:
            pytest.fail("FilterDialog class not implemented")

        tags = ["TagA", "TagB", "TagC"]
        dialog = FilterDialog(available_tags=tags)
        return dialog

    def test_init_populates_tags(self, dialog):
        """Test that available tags are populated in the lists."""
        # Access widgets via the embedded filter_widget

        # Checking include list
        items_in = dialog.filter_widget.list_include.findItems("TagA", Qt.MatchExactly)
        assert len(items_in) > 0

        # Checking exclude list
        items_ex = dialog.filter_widget.list_exclude.findItems("TagB", Qt.MatchExactly)
        assert len(items_ex) > 0

    def test_get_config_defaults(self, dialog):
        """Test default configuration logic."""
        config = dialog.get_filter_config()

        assert config["include"] == []
        assert config["include_mode"] == "any"
        assert config["exclude"] == []
        assert config["exclude_mode"] == "any"
        assert config["case_sensitive"] is False

    def test_selection_generates_config(self, dialog):
        """Test that selecting items produces correct config."""

        # Access widgets via filter_widget

        # Simons selecting TagA in include
        item_a = dialog.filter_widget.list_include.findItems("TagA", Qt.MatchExactly)[0]
        item_a.setCheckState(Qt.Checked)

        # Simons selecting TagB in exclude
        item_b = dialog.filter_widget.list_exclude.findItems("TagB", Qt.MatchExactly)[0]
        item_b.setCheckState(Qt.Checked)

        # Change modes
        dialog.filter_widget.radio_include_all.setChecked(True)
        dialog.filter_widget.radio_exclude_any.setChecked(True)  # default

        config = dialog.get_filter_config()

        assert "TagA" in config["include"]
        assert "TagB" not in config["include"]
        assert config["include_mode"] == "all"

        assert "TagB" in config["exclude"]
        assert config["exclude_mode"] == "any"
