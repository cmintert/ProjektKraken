"""Tests for ID-only marker icon metadata and catalog resolution."""

from pathlib import Path

import pytest

from src.core.marker_appearance import MARKER_ICON_ID_ATTRIBUTE
from src.core.marker_icon import (
    MarkerIconDefinition,
    MarkerIconSource,
    custom_icon_id_from_asset_path,
)
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSource,
)
from src.services.marker_icon_catalog import MarkerIconCatalog


def test_bundled_manifest_exposes_stable_names() -> None:
    catalog = MarkerIconCatalog.load()
    castle = catalog.resolve_id("place.castle")

    assert castle is not None
    assert castle.name == "Castle"
    assert castle.asset_path == "building-castle.svg"
    assert catalog.asset_file(castle).name == "building-castle.svg"


def test_manifest_defines_every_bundled_marker_icon() -> None:
    catalog = MarkerIconCatalog.load()
    manifest_paths = {definition.asset_path for definition in catalog.defaults()}
    bundled_root = catalog.asset_file(catalog.default_definition()).parent
    bundled_paths = {path.name for path in bundled_root.glob("*.svg")}

    assert manifest_paths == bundled_paths


def test_new_marker_attributes_store_only_id_and_default_provenance() -> None:
    attributes = MarkerIconCatalog.load().new_marker_attributes(1000.0)

    assert attributes[MARKER_ICON_ID_ATTRIBUTE] == "map.pin"
    assert "icon" not in attributes
    assert attributes[MARKER_SIZING_SOURCE_ATTRIBUTE] == (
        MarkerSizingSource.ICON_DEFAULT.value
    )
    assert attributes[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(2.5)


def test_project_icon_gets_stable_id_across_catalog_reloads(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    uuid_hex = "0123456789abcdef0123456789abcdef"
    asset = images / f"icon_{uuid_hex}.svg"
    asset.write_text("<svg/>", encoding="utf-8")

    first = MarkerIconCatalog.load(tmp_path)
    second = MarkerIconCatalog.load(tmp_path)
    definition = first.resolve_id(f"custom.{uuid_hex}")

    assert definition is not None
    assert definition.source is MarkerIconSource.CUSTOM
    assert second.resolve_id(definition.id) == definition
    assert first.asset_file(definition) == asset


def test_noncanonical_project_icon_is_not_discovered(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "icon_abc.svg").write_text("<svg/>", encoding="utf-8")

    assert MarkerIconCatalog.load(tmp_path).custom() == ()


def test_custom_id_is_derived_only_from_canonical_import_path() -> None:
    path = "assets/images/icon_0123456789abcdef0123456789abcdef.webp"

    assert custom_icon_id_from_asset_path(path) == (
        "custom.0123456789abcdef0123456789abcdef"
    )
    assert custom_icon_id_from_asset_path("assets/images/icon_short.webp") is None


def test_definition_rejects_unsafe_asset_path() -> None:
    with pytest.raises(ValueError):
        MarkerIconDefinition.from_dict(
            {
                "id": "bad",
                "name": "Bad",
                "asset_path": "../outside.svg",
                "source": "default",
            }
        )


def test_path_only_attributes_are_ignored() -> None:
    catalog = MarkerIconCatalog.load()
    definition = catalog.resolve_attributes({"icon": "building-castle.svg"})

    assert definition is None


def test_unknown_id_uses_default_definition() -> None:
    definition = MarkerIconCatalog.load().definition_or_default("missing.icon")

    assert definition.id == "map.pin"
