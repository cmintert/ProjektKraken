"""Unit tests for enhanced ObsidianExporter features.

Tests the attribute filtering, summary prepending, and single-item
export capabilities added for bidirectional Obsidian integration.
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
        return self._entities

    def get_all_events(self) -> list:
        """Return mock events."""
        return self._events

    def get_relations(self, source_id: str) -> list:
        """Return mock relations for a source ID."""
        return self._relations.get(source_id, [])


class TestAttributeFiltering:
    """Tests for user-defined attribute export and internal key filtering."""

    def test_user_attributes_exported_as_yaml(self):
        """Test that user-defined attributes appear in YAML frontmatter."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-1",
            name="Knight",
            type="character",
            attributes={
                "allegiance": "Highland Kingdom",
                "rank": "Captain",
                "_tags": ["hero"],
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])
        assert 'allegiance: "Highland Kingdom"' in result
        assert 'rank: "Captain"' in result

    def test_internal_attributes_excluded(self):
        """Test that keys starting with _ are omitted from YAML."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-2",
            name="Knight",
            type="character",
            attributes={
                "_import_sources": [{"source": "test"}],
                "_summary_data": {"text": "A summary"},
                "_tags": ["hero"],
                "allegiance": "Highland Kingdom",
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])
        assert "_import_sources" not in result
        assert "_summary_data" not in result
        assert "_tags" not in result
        assert "allegiance" in result

    def test_event_user_attributes_exported(self):
        """Test that event user-defined attributes appear in YAML."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="ev-1",
            name="Battle",
            type="battle",
            lore_date=100.0,
            attributes={
                "location": "Northern Pass",
                "_tags": ["war"],
                "_import_sources": [],
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_event_markdown(event, [])
        assert 'location: "Northern Pass"' in result
        assert "_import_sources" not in result


class TestSummaryPrepending:
    """Tests for summary blockquote prepending."""

    def test_summary_prepended_as_blockquote(self):
        """Test that _summary_data text is prepended as blockquote."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-3",
            name="Ranger",
            type="character",
            description="Long description here.",
            attributes={
                "_summary_data": {
                    "text": "A legendary tracker.",
                    "hash": "abc",
                    "timestamp": 100.0,
                    "model": "test",
                },
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])
        assert "> **Summary**: A legendary tracker." in result
        # Summary should come before description
        summary_pos = result.index("> **Summary**")
        desc_pos = result.index("Long description here.")
        assert summary_pos < desc_pos

    def test_no_summary_no_blockquote(self):
        """Test that no blockquote is added when _summary_data is absent."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="test-4",
            name="Simple",
            type="character",
            description="Just a description.",
            attributes={},
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_entity_markdown(entity, [])
        assert "> **Summary**" not in result

    def test_event_summary_prepended(self):
        """Test that event _summary_data is prepended as blockquote."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="ev-2",
            name="Thaw",
            type="generic",
            lore_date=200.0,
            description="The ice broke.",
            attributes={
                "_summary_data": {
                    "text": "Ice receded from the north.",
                    "hash": "def",
                    "timestamp": 200.0,
                    "model": "test",
                },
            },
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        result = exporter._build_event_markdown(event, [])
        assert "> **Summary**: Ice receded from the north." in result


class TestSingleItemExport:
    """Tests for exporting a single entity or event."""

    def test_export_single_entity(self):
        """Test exporting a single entity to a file."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="ent-single",
            name="Solo Entity",
            type="character",
            description="A standalone entity.",
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_single_item(entity, Path(tmpdir))
            assert filepath is not None
            assert filepath.exists()
            content = filepath.read_text(encoding="utf-8")
            assert 'uid: "ent-single"' in content
            assert 'title: "Solo Entity"' in content

    def test_export_single_event(self):
        """Test exporting a single event to a file."""
        db = MockDbService()
        exporter = ObsidianExporter(db)

        event = Event(
            id="ev-single",
            name="Solo Event",
            type="battle",
            lore_date=500.0,
            description="A standalone event.",
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_single_item(event, Path(tmpdir))
            assert filepath is not None
            assert filepath.exists()
            content = filepath.read_text(encoding="utf-8")
            assert 'uid: "ev-single"' in content
            assert "lore_date: 500.0" in content

    def test_export_single_with_relations(self):
        """Test single-item export includes relations."""
        relations = {"ent-rel": [{"target_id": "ent-target", "rel_type": "ally"}]}
        entities = [
            Entity(
                id="ent-target",
                name="Ally Entity",
                type="character",
                created_at=1705320000.0,
                modified_at=1705320000.0,
            ),
        ]
        db = MockDbService(entities=entities, relations=relations)
        exporter = ObsidianExporter(db)

        entity = Entity(
            id="ent-rel",
            name="Main Entity",
            type="character",
            description="Has relations.",
            created_at=1705320000.0,
            modified_at=1705320000.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_single_item(
                entity, Path(tmpdir), include_relations=True
            )
            content = filepath.read_text(encoding="utf-8")
            assert "## Related" in content
            assert "[[Ally Entity]]" in content
