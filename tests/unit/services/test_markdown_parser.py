"""Unit tests for the Markdown Parser.

Tests the markdown_parser module for:
- YAML frontmatter extraction
- Summary blockquote parsing
- Description body extraction
- Related section and wiki-link parsing
- Conversion to import-ready data
- Entity vs Event detection
"""

from src.services.markdown_parser import (
    ParsedMarkdown,
    is_entity_data,
    markdown_to_import_data,
    parse_markdown,
)


OPTIMAL_TEMPLATE = '''\
---
uid: "a1-b2-c3-d4"
title: "The Silver Ranger"
type: "Entity"
tags: [Hero, Wanderer]
allegiance: "Highland Kingdom"
---

> **Summary**: A legendary tracker known for guarding the northern passes.

# Description
The Silver Ranger first appeared during the Great Thaw, carrying a message for the Citadel.

## Related
- mentor: [[The Grey Archmage]]
- rival: [[Shadow Blade]]
'''

EVENT_TEMPLATE = '''\
---
uid: "ev-001"
title: "The Great Thaw"
type: "battle"
tags: [War, Epic]
lore_date: 3019.5
lore_duration: 0.5
---

> **Summary**: The ice broke across the northern frontier.

# Description
A pivotal moment when the glaciers receded.
'''

MINIMAL_ENTITY = '''\
---
title: "Unnamed Hero"
type: "character"
---

A brief description.
'''


class TestParseMarkdownFrontmatter:
    """Tests for YAML frontmatter extraction."""

    def test_extracts_uid(self):
        """Test that uid is extracted from frontmatter."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.yaml_metadata["uid"] == "a1-b2-c3-d4"

    def test_extracts_title(self):
        """Test that title is extracted from frontmatter."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.yaml_metadata["title"] == "The Silver Ranger"

    def test_extracts_type(self):
        """Test that type is extracted from frontmatter."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.yaml_metadata["type"] == "Entity"

    def test_extracts_tags(self):
        """Test that tags list is extracted from frontmatter."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.yaml_metadata["tags"] == ["Hero", "Wanderer"]

    def test_extracts_custom_attributes(self):
        """Test that user-defined attributes are preserved."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.yaml_metadata["allegiance"] == "Highland Kingdom"

    def test_empty_frontmatter(self):
        """Test parsing with no frontmatter."""
        parsed = parse_markdown("Just a body with no frontmatter.")
        assert parsed.yaml_metadata == {}
        assert parsed.description == "Just a body with no frontmatter."


class TestParseMarkdownSummary:
    """Tests for summary blockquote extraction."""

    def test_extracts_summary_text(self):
        """Test that summary blockquote is extracted."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert parsed.tl_dr_block == (
            "A legendary tracker known for guarding the northern passes."
        )

    def test_no_summary_returns_empty(self):
        """Test that missing summary returns empty string."""
        parsed = parse_markdown(MINIMAL_ENTITY)
        assert parsed.tl_dr_block == ""

    def test_summary_removed_from_description(self):
        """Test that summary line is not in the description."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert "Summary" not in parsed.description
        assert "legendary tracker" not in parsed.description


class TestParseMarkdownDescription:
    """Tests for description body extraction."""

    def test_extracts_description(self):
        """Test that description body text is extracted."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert "Silver Ranger first appeared" in parsed.description

    def test_description_header_stripped(self):
        """Test that # Description header is removed."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert not parsed.description.startswith("# Description")

    def test_minimal_description(self):
        """Test description from minimal template."""
        parsed = parse_markdown(MINIMAL_ENTITY)
        assert parsed.description == "A brief description."


class TestParseMarkdownRelations:
    """Tests for related section parsing."""

    def test_extracts_relations(self):
        """Test that related entries are extracted."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert len(parsed.relations) == 2

    def test_relation_types(self):
        """Test that relation types are correctly parsed."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        types = [r["rel_type"] for r in parsed.relations]
        assert "mentor" in types
        assert "rival" in types

    def test_relation_targets(self):
        """Test that relation target names are correctly parsed."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        targets = [r["target_name"] for r in parsed.relations]
        assert "The Grey Archmage" in targets
        assert "Shadow Blade" in targets

    def test_no_relations_returns_empty(self):
        """Test that missing related section returns empty list."""
        parsed = parse_markdown(MINIMAL_ENTITY)
        assert parsed.relations == []

    def test_related_section_removed_from_description(self):
        """Test that Related section is not in the description."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        assert "## Related" not in parsed.description
        assert "Grey Archmage" not in parsed.description


class TestMarkdownToImportData:
    """Tests for converting parsed markdown to import data."""

    def test_uid_maps_to_id(self):
        """Test that YAML uid maps to import data id."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert data["id"] == "a1-b2-c3-d4"

    def test_title_maps_to_name(self):
        """Test that YAML title maps to import data name."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert data["name"] == "The Silver Ranger"

    def test_tags_stored_in_attributes(self):
        """Test that tags are stored in attributes._tags."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert data["attributes"]["_tags"] == ["Hero", "Wanderer"]

    def test_custom_attributes_preserved(self):
        """Test that user-defined YAML keys become attributes."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert data["attributes"]["allegiance"] == "Highland Kingdom"

    def test_summary_stored_as_summary_data(self):
        """Test that summary is stored as _summary_data attribute."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        summary = data["attributes"]["_summary_data"]
        assert summary["text"] == (
            "A legendary tracker known for guarding the northern passes."
        )

    def test_description_preserved(self):
        """Test that description is preserved in import data."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert "Silver Ranger first appeared" in data["description"]

    def test_relations_converted(self):
        """Test that relations are included in import data."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert len(data["relations"]) == 2

    def test_event_data_includes_lore_date(self):
        """Test that event YAML includes lore_date."""
        parsed = parse_markdown(EVENT_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert data["lore_date"] == 3019.5
        assert data["lore_duration"] == 0.5

    def test_no_uid_omits_id(self):
        """Test that missing uid omits id from import data."""
        parsed = parse_markdown(MINIMAL_ENTITY)
        data = markdown_to_import_data(parsed)
        assert "id" not in data


class TestIsEntityData:
    """Tests for entity vs event detection."""

    def test_entity_data_detected(self):
        """Test that data without lore_date is detected as entity."""
        parsed = parse_markdown(OPTIMAL_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert is_entity_data(data) is True

    def test_event_data_detected(self):
        """Test that data with lore_date is detected as event."""
        parsed = parse_markdown(EVENT_TEMPLATE)
        data = markdown_to_import_data(parsed)
        assert is_entity_data(data) is False
