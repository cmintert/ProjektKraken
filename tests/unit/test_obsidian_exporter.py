"""
Unit tests for the Obsidian Exporter Service.

Tests the ObsidianExporter class for:
- YAML frontmatter generation
- Filename sanitization with duplicate counter
- Body content with wiki-links
- Related section from relations
"""

import tempfile
from pathlib import Path

from src.core.entities import Entity
from src.core.events import Event
from src.services.obsidian_exporter import ObsidianExporter


class MockDbService:
    """Mock database service for testing."""

    def __init__(
        self,
        entities: list | None = None,
        events: list | None = None,
        relations: dict | None = None,
    ):
        """Initialize with test data."""
        self._entities = entities or []
        self._events = events or []
        self._relations = relations or {}

    def get_all_entities(self) -> list:
        """Return mock entities."""
        # Ensure we return valid Entity objects if dicts were passed (for backwards compat in test setups)
        # But for this test update, we expect the caller to pass objects mostly.
        # Actually, let's just return what is passed, assuming tests are updated.
        return self._entities

    def get_all_events(self) -> list:
        """Return mock events."""
        return self._events

    def get_relations(self, source_id: str) -> list:
        """
        Return mock relations for a source ID.
        Relations are returned as List[Dict], consistent with DatabaseService.
        """
        return self._relations.get(source_id, [])


class TestObsidianExporterFilename:
    """Tests for filename sanitization and duplicate handling."""

    def test_sanitize_filename_removes_invalid_chars(self):
        """Test that invalid filesystem characters are removed."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        assert exporter._sanitize_filename('Test<>:"/\\|?*Name') == "TestName"
        assert exporter._sanitize_filename("Normal Name") == "Normal Name"

    def test_sanitize_filename_empty_returns_untitled(self):
        """Test that empty name returns 'Untitled'."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        assert exporter._sanitize_filename("") == "Untitled"
        assert exporter._sanitize_filename("   ") == "Untitled"
        assert exporter._sanitize_filename("...") == "Untitled"

    def test_unique_filename_first_occurrence(self):
        """Test first occurrence gets simple .md extension."""
        db = MockDbService()
        exporter = ObsidianExporter(db)
        used = {}

        result = exporter._get_unique_filename("Test", used)
        assert result == "Test.md"
        assert used["Test"] == 1

    def test_unique_filename_duplicates_get_counter(self):
        """Test duplicate names get incremented counter."""
        db = MockDbService()
        exporter = ObsidianExporter(db)
        used = {}

        assert exporter._get_unique_filename("Test", used) == "Test.md"
        assert exporter._get_unique_filename("Test", used) == "Test (2).md"
        assert exporter._get_unique_filename("Test", used) == "Test (3).md"

    def test_unique_filename_different_names_independent(self):
        """Test different names are tracked independently."""
        db = MockDbService()
        exporter = ObsidianExporter(db)
        used = {}

        assert exporter._get_unique_filename("Alpha", used) == "Alpha.md"
        assert exporter._get_unique_filename("Beta", used) == "Beta.md"
        assert exporter._get_unique_filename("Alpha", used) == "Alpha (2).md"


class TestObsidianExporterFrontmatter:
    """Tests for YAML frontmatter generation."""

    def test_entity_frontmatter_basic_fields(self):
        """Test entity markdown includes required frontmatter fields."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-123",
            name="Test Entity",
            type="character",
            description="A test character.",
            created_at=1705320000.0,
            modified_at=1705406400.0,
        )

        result = exporter._build_entity_markdown(entity, [])

        assert "---" in result
        assert 'title: "Test Entity"' in result
        assert "type: character" in result
        assert 'uid: "test-123"' in result
        assert "source: ProjektKraken" in result
        assert "A test character." in result

    def test_entity_frontmatter_with_tags(self):
        """Test entity markdown includes tags when present."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-123",
            name="Tagged Entity",
            type="location",
            attributes={"_tags": ["important", "main-plot"]},
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])

        assert "tags:" in result
        assert "  - important" in result
        assert "  - main-plot" in result

    def test_event_frontmatter_includes_lore_date(self):
        """Test event markdown includes lore_date and lore_duration."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="event-456",
            name="Battle of Test",
            type="battle",
            lore_date=3019.5,
            lore_duration=0.5,
            description="An epic battle.",
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_event_markdown(event, [])

        assert "lore_date: 3019.5" in result
        assert "lore_duration: 0.5" in result
        assert "An epic battle." in result


class TestObsidianExporterRelations:
    """Tests for related section generation."""

    def test_entity_with_relations(self):
        """Test entity markdown includes Related section with wiki-links."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-123",
            name="Test Entity",
            type="character",
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        relations = [
            {"name": "Friend Character", "rel_type": "ally"},
            {"name": "Enemy Character", "rel_type": "enemy"},
        ]

        result = exporter._build_entity_markdown(entity, relations)

        assert "## Related" in result
        assert "- ally: [[Friend Character]]" in result
        assert "- enemy: [[Enemy Character]]" in result

    def test_event_without_relations_no_section(self):
        """Test event markdown omits Related section when no relations."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="event-456",
            name="Solo Event",
            type="generic",
            lore_date=100.0,
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_event_markdown(event, [])

        assert "## Related" not in result


class TestObsidianExporterExport:
    """Tests for the full export_to_folder operation."""

    def test_export_creates_files(self):
        """Test export creates files for entities and events."""
        entities = [
            Entity(
                id="e1",
                name="Entity One",
                type="character",
                description="First entity",
                attributes={},
                created_at=1705320000.0,
                modified_at=1705320000.0,
            )
        ]
        events = [
            Event(
                id="ev1",
                name="Event One",
                type="generic",
                description="First event",
                lore_date=100.0,
                lore_duration=0.0,
                attributes={},
                created_at=1705320000.0,
                modified_at=1705320000.0,
            )
        ]

        db = MockDbService(entities=entities, events=events)
        exporter = ObsidianExporter(db)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = exporter.export_to_folder(output_dir)

            assert result.success is True
            assert result.files_created == 2
            assert (output_dir / "Entity One.md").exists()
            assert (output_dir / "Event One.md").exists()

    def test_export_handles_duplicate_names(self):
        """Test export handles entities with same name."""
        entities = [
            Entity(
                id="e1",
                name="Duplicate",
                type="character",
                description="",
                attributes={},
                created_at=1705320000.0,
                modified_at=1705320000.0,
            ),
            Entity(
                id="e2",
                name="Duplicate",
                type="location",
                description="",
                attributes={},
                created_at=1705320000.0,
                modified_at=1705320000.0,
            ),
        ]

        db = MockDbService(entities=entities, events=[])
        exporter = ObsidianExporter(db)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = exporter.export_to_folder(output_dir)

            assert result.success is True
            assert result.files_created == 2
            assert (output_dir / "Duplicate.md").exists()
            assert (output_dir / "Duplicate (2).md").exists()


class TestObsidianExporterYamlEscape:
    """Tests for YAML string escaping."""

    def test_escape_quotes(self):
        """Test double quotes are escaped in YAML strings."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        assert exporter._escape_yaml_string("Normal") == "Normal"
        assert exporter._escape_yaml_string('Say "Hello"') == 'Say \\"Hello\\"'


class TestObsidianExporterStatBlock:
    """Tests for the [!stat] callout block generation from sheet layout."""

    def test_no_layout_returns_none(self):
        """Test that _build_stat_block returns None when no layout exists."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        result = exporter._build_stat_block("Hero", {"STR": 18})
        assert result is None

    def test_single_key_row(self):
        """Test single-key row renders as '> **Key:** Value'."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        attrs = {"Name": "Aragorn", "_sheet_layout": [["Name"]]}
        result = exporter._build_stat_block("Hero", attrs)

        assert result is not None
        assert "> [!stat] Hero" in result
        assert "> **Name:** Aragorn" in result

    def test_multi_key_row(self):
        """Test multi-key row renders as pipe-separated values."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        attrs = {
            "STR": 18,
            "DEX": 14,
            "CON": 16,
            "_sheet_layout": [["STR", "DEX", "CON"]],
        }
        result = exporter._build_stat_block("Fighter", attrs)

        assert result is not None
        assert "> [!stat] Fighter" in result
        assert "> **STR:** 18 | **DEX:** 14 | **CON:** 16" in result

    def test_mixed_rows(self):
        """Test layout with single and multi-key rows."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        attrs = {
            "Name": "Gandalf",
            "Class": "Wizard",
            "STR": 10,
            "INT": 20,
            "_sheet_layout": [["Name"], ["Class"], ["STR", "INT"]],
        }
        result = exporter._build_stat_block("Gandalf", attrs)

        lines = result.split("\n")
        assert lines[0] == "> [!stat] Gandalf"
        assert lines[1] == "> **Name:** Gandalf"
        assert lines[2] == "> **Class:** Wizard"
        assert lines[3] == "> **STR:** 10 | **INT:** 20"

    def test_missing_key_uses_empty_value(self):
        """Test that layout keys not in attrs use empty string."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        attrs = {"STR": 18, "_sheet_layout": [["STR", "MISSING"]]}
        result = exporter._build_stat_block("Hero", attrs)

        assert "> **STR:** 18 | **MISSING:** " in result

    def test_entity_markdown_includes_stat_block(self):
        """Test that entity markdown includes stat block when layout exists."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="e1",
            name="Fighter",
            type="character",
            description="A brave warrior.",
            attributes={
                "STR": 18,
                "DEX": 14,
                "_sheet_layout": [["STR", "DEX"]],
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])
        assert "> [!stat] Fighter" in result
        assert "> **STR:** 18 | **DEX:** 14" in result

    def test_event_markdown_includes_stat_block(self):
        """Test that event markdown includes stat block when layout exists."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="ev1",
            name="Battle",
            type="combat",
            lore_date=100.0,
            description="An epic battle.",
            attributes={
                "Difficulty": "Hard",
                "_sheet_layout": [["Difficulty"]],
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_event_markdown(event, [])
        assert "> [!stat] Battle" in result
        assert "> **Difficulty:** Hard" in result

    def test_empty_layout_no_stat_block(self):
        """Test that empty layout list produces no stat block."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        result = exporter._build_stat_block("Hero", {"_sheet_layout": []})
        assert result is None

    def test_invalid_layout_type_returns_none(self):
        """Test that non-list layout value returns None."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        result = exporter._build_stat_block("Hero", {"_sheet_layout": "invalid"})
        assert result is None
