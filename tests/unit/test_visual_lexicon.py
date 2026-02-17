"""Tests for the Visual Lexicon System.

Tests cover:
- Phase A: Schema Discovery (get_lexicon_schema)
- Phase B: Asset Importing (import_asset_file)
- Phase C: Database Persistence (get_graph_lexicon / set_graph_lexicon)
- Phase D: Graph Rendering (prepare_node/prepare_edge with lexicon, Base64 encoding)
"""

import base64
import os
import tempfile
from pathlib import Path

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.map.icon_picker_dialog import (
    ALLOWED_IMAGE_EXTENSIONS,
    import_asset_file,
)
from src.services.db_service import DatabaseService
from src.services.graph_data_service import GraphDataService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_service():
    """Provides a DatabaseService with in-memory database."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture
def populated_db(db_service):
    """Populates db with test entities, events, and relations."""
    entity1 = Entity(name="Deity Alpha", type="deity")
    entity1.tags = ["divine"]
    db_service.insert_entity(entity1)

    entity2 = Entity(name="Starship Beta", type="starship")
    entity2.tags = ["vehicle"]
    db_service.insert_entity(entity2)

    entity3 = Entity(name="Faction Gamma", type="faction")
    entity3.tags = ["political"]
    db_service.insert_entity(entity3)

    event1 = Event(name="The Great War", lore_date=1000.0)
    db_service.insert_event(event1)

    db_service.insert_relation(entity1.id, entity2.id, "allied_with")
    db_service.insert_relation(entity2.id, entity3.id, "enemy_of")

    return {
        "db": db_service,
        "entities": [entity1, entity2, entity3],
        "events": [event1],
    }


@pytest.fixture
def temp_assets_dir(tmp_path):
    """Provides a temporary assets directory."""
    assets = tmp_path / "assets"
    assets.mkdir()
    return assets


@pytest.fixture
def sample_svg(tmp_path):
    """Creates a sample SVG file for import testing."""
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
    svg_file = tmp_path / "dragon.svg"
    svg_file.write_text(svg_content)
    return svg_file


# ---------------------------------------------------------------------------
# Phase A: Schema Discovery
# ---------------------------------------------------------------------------


class TestGetLexiconSchema:
    """Tests for GraphDataService.get_lexicon_schema method."""

    def test_returns_entity_and_relation_types(self, populated_db):
        """Returns dict with entity_types and relation_types keys."""
        service = GraphDataService()
        schema = service.get_lexicon_schema(populated_db["db"])

        assert "entity_types" in schema
        assert "relation_types" in schema

    def test_entity_types_are_correct(self, populated_db):
        """Entity types match what was inserted."""
        service = GraphDataService()
        schema = service.get_lexicon_schema(populated_db["db"])

        assert set(schema["entity_types"]) == {"deity", "starship", "faction"}

    def test_relation_types_are_correct(self, populated_db):
        """Relation types match what was inserted."""
        service = GraphDataService()
        schema = service.get_lexicon_schema(populated_db["db"])

        assert set(schema["relation_types"]) == {"allied_with", "enemy_of"}

    def test_empty_database_returns_empty_lists(self, db_service):
        """Returns empty lists for a database with no data."""
        service = GraphDataService()
        schema = service.get_lexicon_schema(db_service)

        assert schema["entity_types"] == []
        assert schema["relation_types"] == []

    def test_types_are_sorted(self, populated_db):
        """Types are returned sorted alphabetically."""
        service = GraphDataService()
        schema = service.get_lexicon_schema(populated_db["db"])

        assert schema["entity_types"] == sorted(schema["entity_types"])
        assert schema["relation_types"] == sorted(schema["relation_types"])


# ---------------------------------------------------------------------------
# Phase B: Asset Importing
# ---------------------------------------------------------------------------


class TestImportAssetFile:
    """Tests for the import_asset_file function."""

    def test_import_svg_success(self, sample_svg, temp_assets_dir):
        """Successfully imports an SVG file and returns relative path."""
        result = import_asset_file(str(sample_svg), temp_assets_dir)

        assert result is not None
        assert result.startswith("assets/images/icon_")
        assert result.endswith(".svg")

    def test_import_creates_images_directory(self, sample_svg, tmp_path):
        """Creates the images subdirectory if it doesn't exist."""
        assets = tmp_path / "new_assets"
        assets.mkdir()

        result = import_asset_file(str(sample_svg), assets)

        assert result is not None
        assert (assets / "images").is_dir()

    def test_imported_file_exists(self, sample_svg, temp_assets_dir):
        """The imported file actually exists on disk."""
        result = import_asset_file(str(sample_svg), temp_assets_dir)

        # Resolve relative to parent of assets_dir (world root)
        world_root = temp_assets_dir.parent
        full_path = world_root / result
        assert full_path.exists()

    def test_import_png_allowed(self, tmp_path, temp_assets_dir):
        """PNG files are allowed for import."""
        png_file = tmp_path / "test.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        result = import_asset_file(str(png_file), temp_assets_dir)

        assert result is not None
        assert result.endswith(".png")

    def test_import_jpg_allowed(self, tmp_path, temp_assets_dir):
        """JPG files are allowed for import."""
        jpg_file = tmp_path / "test.jpg"
        jpg_file.write_bytes(b"\xff\xd8\xff")

        result = import_asset_file(str(jpg_file), temp_assets_dir)

        assert result is not None
        assert result.endswith(".jpg")

    def test_import_exe_blocked(self, tmp_path, temp_assets_dir):
        """Executable files are blocked from import."""
        exe_file = tmp_path / "malware.exe"
        exe_file.write_bytes(b"MZ")

        result = import_asset_file(str(exe_file), temp_assets_dir)

        assert result is None

    def test_import_html_blocked(self, tmp_path, temp_assets_dir):
        """HTML files are blocked from import."""
        html_file = tmp_path / "xss.html"
        html_file.write_text("<script>alert('xss')</script>")

        result = import_asset_file(str(html_file), temp_assets_dir)

        assert result is None

    def test_import_nonexistent_file(self, temp_assets_dir):
        """Returns None for non-existent source file."""
        result = import_asset_file("/nonexistent/path/file.svg", temp_assets_dir)

        assert result is None

    def test_collision_free_filenames(self, sample_svg, temp_assets_dir):
        """Multiple imports generate unique filenames."""
        result1 = import_asset_file(str(sample_svg), temp_assets_dir)
        result2 = import_asset_file(str(sample_svg), temp_assets_dir)

        assert result1 is not None
        assert result2 is not None
        assert result1 != result2

    def test_allowed_extensions_constant(self):
        """The ALLOWED_IMAGE_EXTENSIONS constant includes expected types."""
        assert ".svg" in ALLOWED_IMAGE_EXTENSIONS
        assert ".png" in ALLOWED_IMAGE_EXTENSIONS
        assert ".jpg" in ALLOWED_IMAGE_EXTENSIONS
        assert ".jpeg" in ALLOWED_IMAGE_EXTENSIONS
        assert ".exe" not in ALLOWED_IMAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# Phase C: Database Persistence
# ---------------------------------------------------------------------------


class TestGraphLexiconPersistence:
    """Tests for get_graph_lexicon / set_graph_lexicon in DatabaseService."""

    def test_get_lexicon_returns_none_when_empty(self, db_service):
        """Returns None when no lexicon is configured."""
        result = db_service.get_graph_lexicon()

        assert result is None

    def test_set_and_get_lexicon_roundtrip(self, db_service):
        """Data survives a set/get roundtrip."""
        lexicon = {
            "nodes": {
                "Faction": {"color": "#FFD700", "shape": "image", "icon": "a.svg"}
            },
            "edges": {
                "enemy_of": {"color": "#FF0000", "width": 3, "dashes": True}
            },
        }

        db_service.set_graph_lexicon(lexicon)
        result = db_service.get_graph_lexicon()

        assert result == lexicon

    def test_set_lexicon_overwrites_previous(self, db_service):
        """Setting a new lexicon replaces the previous one."""
        db_service.set_graph_lexicon({"nodes": {"A": {"color": "#111"}}})
        db_service.set_graph_lexicon({"nodes": {"B": {"color": "#222"}}})

        result = db_service.get_graph_lexicon()

        assert "B" in result["nodes"]
        assert "A" not in result["nodes"]

    def test_empty_lexicon_allowed(self, db_service):
        """An empty dict can be stored and retrieved."""
        db_service.set_graph_lexicon({"nodes": {}, "edges": {}})
        result = db_service.get_graph_lexicon()

        assert result == {"nodes": {}, "edges": {}}

    def test_complex_lexicon_structure(self, db_service):
        """Complex nested structures survive serialization."""
        lexicon = {
            "nodes": {
                "Character": {"color": "#00FF00", "shape": "dot"},
                "Location": {"color": "#0000FF", "shape": "box"},
                "Deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                },
            },
            "edges": {
                "allied_with": {"color": "#00FF00", "width": 2, "dashes": False},
                "enemy_of": {"color": "#FF0000", "width": 3, "dashes": True},
            },
        }

        db_service.set_graph_lexicon(lexicon)
        result = db_service.get_graph_lexicon()

        assert result == lexicon


# ---------------------------------------------------------------------------
# Phase D: Graph Rendering (prepare_node / prepare_edge with lexicon)
# ---------------------------------------------------------------------------


class TestPrepareNodeWithLexicon:
    """Tests for GraphBuilder.prepare_node with lexicon support."""

    def test_default_behavior_without_lexicon(self):
        """Without lexicon, node uses default colors and shapes."""
        node = {"id": "1", "name": "Alice", "object_type": "entity", "type": "human"}
        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA")

        assert result["color"] == "#CCC"
        assert result["shape"] == GraphBuilder.ENTITY_SHAPE

    def test_lexicon_overrides_color(self):
        """Lexicon color overrides the default entity color."""
        node = {"id": "1", "name": "Zeus", "object_type": "entity", "type": "deity"}
        lexicon = {"deity": {"color": "#FFD700"}}

        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA", lexicon=lexicon)

        assert result["color"] == "#FFD700"

    def test_lexicon_overrides_shape(self):
        """Lexicon shape overrides the default shape."""
        node = {"id": "1", "name": "HQ", "object_type": "entity", "type": "location"}
        lexicon = {"location": {"shape": "box"}}

        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA", lexicon=lexicon)

        assert result["shape"] == "box"

    def test_lexicon_image_shape_sets_image(self):
        """When shape is 'image' and image data exists, it's set on the node."""
        data_uri = "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
        node = {"id": "1", "name": "Ship", "object_type": "entity", "type": "ship"}
        lexicon = {"ship": {"shape": "image", "image": data_uri}}

        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA", lexicon=lexicon)

        assert result["shape"] == "image"
        assert result["image"] == data_uri

    def test_lexicon_no_match_uses_defaults(self):
        """When type not in lexicon, defaults are used."""
        node = {"id": "1", "name": "X", "object_type": "entity", "type": "unknown"}
        lexicon = {"deity": {"color": "#FFD700"}}

        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA", lexicon=lexicon)

        assert result["color"] == "#CCC"

    def test_event_node_without_lexicon(self):
        """Event nodes get event color by default."""
        node = {"id": "1", "name": "War", "object_type": "event", "type": "battle"}

        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA")

        assert result["color"] == "#AAA"
        assert result["shape"] == GraphBuilder.EVENT_SHAPE


class TestPrepareEdgeWithLexicon:
    """Tests for GraphBuilder.prepare_edge with lexicon support."""

    def test_default_behavior_without_lexicon(self):
        """Without lexicon, edge uses default color."""
        edge = {"id": "e1", "source_id": "1", "target_id": "2", "rel_type": "likes"}

        result = GraphBuilder.prepare_edge(edge, "#888")

        assert result["color"] == "#888"
        assert "width" not in result
        assert "dashes" not in result

    def test_lexicon_overrides_edge_color(self):
        """Lexicon edge color overrides default."""
        edge = {"id": "e1", "source_id": "1", "target_id": "2", "rel_type": "enemy_of"}
        lexicon = {"enemy_of": {"color": "#FF0000"}}

        result = GraphBuilder.prepare_edge(edge, "#888", lexicon=lexicon)

        assert result["color"] == "#FF0000"

    def test_lexicon_sets_width_and_dashes(self):
        """Lexicon can set width and dashes on edges."""
        edge = {"id": "e1", "source_id": "1", "target_id": "2", "rel_type": "enemy_of"}
        lexicon = {"enemy_of": {"color": "#FF0000", "width": 3, "dashes": True}}

        result = GraphBuilder.prepare_edge(edge, "#888", lexicon=lexicon)

        assert result["width"] == 3
        assert result["dashes"] is True

    def test_lexicon_no_match_uses_defaults(self):
        """When rel_type not in lexicon, defaults are used."""
        edge = {"id": "e1", "source_id": "1", "target_id": "2", "rel_type": "unknown"}
        lexicon = {"enemy_of": {"color": "#FF0000"}}

        result = GraphBuilder.prepare_edge(edge, "#888", lexicon=lexicon)

        assert result["color"] == "#888"


# ---------------------------------------------------------------------------
# Phase D: Base64 Image Encoding
# ---------------------------------------------------------------------------


class TestImageToBase64:
    """Tests for GraphBuilder.image_to_base64 static method."""

    def test_encodes_svg_file(self, tmp_path):
        """Encodes an SVG file to a data URI."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(svg_content)

        result = GraphBuilder.image_to_base64(svg_file)

        assert result.startswith("data:image/svg+xml;base64,")
        # Decode and verify content roundtrip
        encoded_part = result.split(",", 1)[1]
        decoded = base64.b64decode(encoded_part)
        assert decoded == svg_content

    def test_encodes_png_file(self, tmp_path):
        """Encodes a PNG file to a data URI."""
        png_data = b"\x89PNG\r\n\x1a\n"
        png_file = tmp_path / "icon.png"
        png_file.write_bytes(png_data)

        result = GraphBuilder.image_to_base64(png_file)

        assert result.startswith("data:image/png;base64,")

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Returns empty string for non-existent file."""
        result = GraphBuilder.image_to_base64(tmp_path / "ghost.svg")

        assert result == ""

    def test_result_contains_no_file_protocol(self, tmp_path):
        """Data URI never contains file:// protocol."""
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(b"<svg></svg>")

        result = GraphBuilder.image_to_base64(svg_file)

        assert "file://" not in result


class TestResolveLexiconImages:
    """Tests for GraphBuilder.resolve_lexicon_images static method."""

    def test_resolves_icon_to_base64(self, tmp_path):
        """Resolves a relative icon path to a Base64 data URI."""
        # Setup: create icon file at expected location
        images_dir = tmp_path / "assets" / "images"
        images_dir.mkdir(parents=True)
        icon_file = images_dir / "crown.svg"
        icon_file.write_bytes(b"<svg></svg>")

        lexicon = {
            "nodes": {
                "Faction": {
                    "color": "#FFD700",
                    "shape": "dot",
                    "icon": "assets/images/crown.svg",
                }
            },
            "edges": {},
        }

        result = GraphBuilder.resolve_lexicon_images(lexicon, tmp_path)

        assert result["nodes"]["Faction"]["shape"] == "image"
        assert result["nodes"]["Faction"]["image"].startswith("data:")

    def test_missing_icon_does_not_override_shape(self, tmp_path):
        """If icon file doesn't exist, shape is not changed to 'image'."""
        lexicon = {
            "nodes": {
                "Deity": {
                    "color": "#FFD700",
                    "shape": "dot",
                    "icon": "assets/images/nonexistent.svg",
                }
            },
            "edges": {},
        }

        result = GraphBuilder.resolve_lexicon_images(lexicon, tmp_path)

        assert result["nodes"]["Deity"]["shape"] == "dot"

    def test_edges_pass_through_unchanged(self, tmp_path):
        """Edge configuration passes through without modification."""
        lexicon = {
            "nodes": {},
            "edges": {"enemy_of": {"color": "#FF0000", "width": 3}},
        }

        result = GraphBuilder.resolve_lexicon_images(lexicon, tmp_path)

        assert result["edges"]["enemy_of"]["color"] == "#FF0000"
        assert result["edges"]["enemy_of"]["width"] == 3

    def test_node_without_icon_passes_through(self, tmp_path):
        """Nodes without icon key pass through unchanged."""
        lexicon = {
            "nodes": {"Character": {"color": "#00FF00", "shape": "dot"}},
            "edges": {},
        }

        result = GraphBuilder.resolve_lexicon_images(lexicon, tmp_path)

        assert result["nodes"]["Character"]["color"] == "#00FF00"
        assert result["nodes"]["Character"]["shape"] == "dot"
        assert "image" not in result["nodes"]["Character"]
