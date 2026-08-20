"""Tests for the shared ID-only IconPickerDialog."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
from src.gui.dialogs.icon_picker_dialog import IconPickerDialog, remove_project_icon
from src.services.marker_icon_catalog import MarkerIconCatalog


@pytest.fixture
def qapp():
    """Provide a QApplication instance for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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


def test_remove_project_icon_uses_definition(tmp_path):
    uuid_hex = "0123456789abcdef0123456789abcdef"
    definition = _custom_definition(uuid_hex)
    icon_file = tmp_path / definition.asset_path
    icon_file.parent.mkdir(parents=True)
    icon_file.write_text("<svg/>")

    assert remove_project_icon(str(tmp_path), definition)
    assert not icon_file.exists()


def test_remove_project_icon_rejects_bundled_definition(tmp_path):
    definition = MarkerIconDefinition(
        id="map.pin",
        name="Map Pin",
        asset_path="map-pin.svg",
        source=MarkerIconSource.DEFAULT,
    )

    assert not remove_project_icon(str(tmp_path), definition)


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

    def test_icon_buttons_have_neutral_background(self, qapp):
        from src.gui.dialogs.icon_picker_dialog import _ICON_PREVIEW_BG

        dialog = IconPickerDialog()
        btn = dialog._make_icon_button("/fake/icon.svg", "test")
        assert _ICON_PREVIEW_BG in btn.styleSheet()

    def test_import_returns_canonical_definition(self, qapp, tmp_path):
        source = tmp_path / "source.svg"
        source.write_text("<svg/>")
        world_root = tmp_path / "world"
        dialog = IconPickerDialog(world_root=str(world_root))

        with patch.object(dialog, "accept") as accept, patch(
            "src.gui.dialogs.icon_picker_dialog.QFileDialog.getOpenFileName",
            return_value=(str(source), ""),
        ):
            dialog._on_import_clicked()

        definition = dialog.selected_definition
        assert definition is not None
        assert definition.id.startswith("custom.")
        assert definition.source is MarkerIconSource.CUSTOM
        assert accept.called
