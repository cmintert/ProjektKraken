"""Tests for the shared ID-only IconPickerDialog."""

from unittest.mock import patch

from PySide6.QtWidgets import QLabel

from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
from src.gui.dialogs.icon_picker_dialog import IconPickerDialog, ProjectIconCard
from src.services.marker_icon_catalog import MarkerIconCatalog


def _custom_definition(uuid_hex: str, extension: str = ".svg") -> MarkerIconDefinition:
    return MarkerIconDefinition(
        id=f"custom.{uuid_hex}",
        name=f"Project Icon {uuid_hex[:8]}",
        asset_path=f"assets/images/icon_{uuid_hex}{extension}",
        source=MarkerIconSource.CUSTOM,
        category="Project Icons",
    )


def test_catalog_discovers_only_canonical_project_icons(tmp_path):
    images_dir = tmp_path / "assets" / "images"
    images_dir.mkdir(parents=True)
    uuid_hex = "0123456789abcdef0123456789abcdef"
    (images_dir / f"icon_{uuid_hex}.svg").write_text("<svg/>")
    (images_dir / "icon_short.svg").write_text("<svg/>")
    (images_dir / "photo.png").write_bytes(b"PNG")

    definitions = MarkerIconCatalog.load(tmp_path).custom()

    assert [definition.id for definition in definitions] == [f"custom.{uuid_hex}"]


def test_remove_project_icon_requests_usage_before_confirmation(qapp, tmp_path):
    uuid_hex = "0123456789abcdef0123456789abcdef"
    definition = _custom_definition(uuid_hex)
    icon_file = tmp_path / definition.asset_path
    icon_file.parent.mkdir(parents=True)
    icon_file.write_text("<svg/>")

    dialog = IconPickerDialog(world_root=str(tmp_path))
    requests = []
    dialog.library_requested.connect(requests.append)
    dialog._on_remove_project_icon(definition)
    assert requests == [{"operation": "usage", "icon_id": definition.id}]
    assert icon_file.exists()
    dialog.finish_library_request(
        True, "", {"operation": "usage", "report": {"usage": ["Visual Lexicon: Tower"]}}
    )
    assert "Tower" in dialog._status.toPlainText()
    assert len(requests) == 1


def test_bundled_cards_do_not_offer_library_mutations(qapp, tmp_path):
    dialog = IconPickerDialog(world_root=str(tmp_path))
    from PySide6.QtCore import Qt

    for card in dialog._tabs.widget(0).findChildren(ProjectIconCard):
        assert (
            card._icon_btn.contextMenuPolicy()
            == Qt.ContextMenuPolicy.DefaultContextMenu
        )


class TestIconPickerDialogCreation:
    """Tests for IconPickerDialog instantiation and stable selection."""

    def test_creates_without_world_root(self, qapp):
        dialog = IconPickerDialog()
        assert dialog.windowTitle() == "Select Icon"
        assert dialog.selected_definition is None

    def test_creates_with_world_root(self, qapp, tmp_path):
        dialog = IconPickerDialog(world_root=str(tmp_path))
        assert dialog.selected_definition is None

    def test_definition_selection_exposes_only_definition(self, qapp):
        dialog = IconPickerDialog()
        definition = dialog._catalog.resolve_id("place.castle")
        assert definition is not None

        dialog._on_definition_selected(definition)

        assert dialog.selected_definition == definition
        assert not hasattr(dialog, "selected_icon")
        assert not hasattr(dialog, "selected_icon_id")

    def test_picker_shows_human_readable_bundled_names(self, qapp):
        dialog = IconPickerDialog()

        labels = {label.text() for label in dialog.findChildren(QLabel)}

        assert "Castle" in labels
        assert "building-castle.svg" not in labels

    def test_dialog_has_theme_stylesheet(self, qapp):
        dialog = IconPickerDialog()
        assert dialog.styleSheet() != ""

    def test_icon_buttons_have_theme_style(self, qapp):
        from src.gui.utils.style_helper import StyleHelper

        dialog = IconPickerDialog()
        btn = dialog._make_icon_button("/fake/icon.svg", "test")
        assert btn.styleSheet() == StyleHelper.get_tool_button_style()

    def test_import_emits_batch_and_keeps_picker_open(self, qapp, tmp_path):
        source = tmp_path / "source.svg"
        source.write_text("<svg/>")
        world_root = tmp_path / "world"
        dialog = IconPickerDialog(world_root=str(world_root))
        requests = []
        dialog.library_requested.connect(requests.append)

        with (
            patch.object(dialog, "accept") as accept,
            patch(
                "src.gui.dialogs.icon_picker_dialog.QFileDialog.getOpenFileNames",
                return_value=([str(source), str(tmp_path / "second.svg")], ""),
            ),
        ):
            dialog._on_import_clicked()

        assert requests[0]["source_paths"] == [
            str(source),
            str(tmp_path / "second.svg"),
        ]
        assert dialog.selected_definition is None
        assert not accept.called
        assert dialog._pending
        dialog.finish_library_request(
            True,
            "",
            {
                "operation": "import",
                "report": {"added": [{}, {}], "reused": [], "failed": []},
            },
        )
        assert not dialog._pending
        assert "Added 2" in dialog._status.toPlainText()
        assert dialog._tabs.currentIndex() == 1
        assert dialog.selected_definition is None
