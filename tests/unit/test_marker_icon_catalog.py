"""Tests for stable marker icon metadata and legacy resolution."""

from pathlib import Path

import pytest

from src.core.marker_appearance import (
    MARKER_ICON_ATTRIBUTE,
    MARKER_ICON_ID_ATTRIBUTE,
)
from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
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
    assert catalog.resolve_path("building-castle.svg") == castle


def test_new_marker_attributes_store_id_path_and_default_provenance() -> None:
    attributes = MarkerIconCatalog.load().new_marker_attributes(1000.0)

    assert attributes[MARKER_ICON_ID_ATTRIBUTE] == "map.pin"
    assert attributes[MARKER_ICON_ATTRIBUTE] == "map-pin.svg"
    assert attributes[MARKER_SIZING_SOURCE_ATTRIBUTE] == (
        MarkerSizingSource.ICON_DEFAULT.value
    )
    assert attributes[MARKER_SIZING_ATTRIBUTE]["map_value"] == pytest.approx(5.0)


def test_project_icon_gets_safe_non_persistent_legacy_definition(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "icon_abc.svg").write_text("<svg/>", encoding="utf-8")

    catalog = MarkerIconCatalog.load(tmp_path)
    definition = catalog.resolve_path("assets/images/icon_abc.svg")

    assert definition is not None
    assert definition.source is MarkerIconSource.CUSTOM
    assert definition.id == "legacy.custom.icon_abc"


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


def test_resolver_prefers_stable_id_over_legacy_path() -> None:
    catalog = MarkerIconCatalog.load()
    definition = catalog.resolve_attributes(
        {
            MARKER_ICON_ID_ATTRIBUTE: "place.castle",
            MARKER_ICON_ATTRIBUTE: "map-pin.svg",
        }
    )

    assert definition is not None
    assert definition.id == "place.castle"
