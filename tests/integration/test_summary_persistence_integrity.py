"""Integration tests for summary persistence integrity.

Verifies that:
1. Summary generation does not cause destructive partial saves.
2. Editor save flow correctly merges pending summary with hidden attributes.
3. Tags and other hidden attributes are preserved through the save cycle.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import SummaryData
from src.services.summary_service import SummaryService


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider that returns a canned summary."""
    provider = MagicMock()
    provider.generate.return_value = {
        "text": "Generated summary text.",
        "model": "test-model",
        "usage": {"total_tokens": 42},
        "finish_reason": "stop",
    }
    return provider


@pytest.fixture
def summary_service(db_service, mock_llm_provider):
    """SummaryService wired to an in-memory DB with a mock LLM provider."""
    with patch(
        "src.services.summary_service.create_provider",
        return_value=mock_llm_provider,
    ):
        service = SummaryService(db_service)
        service._llm_provider = mock_llm_provider
        return service


class TestSummaryGenerationDoesNotDestroyData:
    """Summary generation must not persist partial data to the database."""

    def test_entity_tags_preserved_after_summary_generation(
        self, db_service, summary_service
    ):
        """Tags on an entity must survive summary generation unchanged."""
        entity = Entity(
            name="Knight",
            type="character",
            description="A loyal knight.",
            attributes={
                "_tags": ["warrior", "noble"],
                "strength": 10,
            },
        )
        db_service.insert_entity(entity)

        # Generate summary (should NOT write to DB)
        summary_service.generate_summary(entity)

        # Reload from DB and verify tags are untouched
        reloaded = db_service.get_entity(entity.id)
        assert reloaded is not None
        assert reloaded.attributes.get("_tags") == ["warrior", "noble"]
        # Original user attribute also intact
        assert reloaded.attributes.get("strength") == 10

    def test_event_tags_preserved_after_summary_generation(
        self, db_service, summary_service
    ):
        """Tags on an event must survive summary generation unchanged."""
        event = Event(
            name="Battle",
            lore_date=500.0,
            description="A great battle.",
            attributes={
                "_tags": ["war", "decisive"],
                "casualties": 5000,
            },
        )
        db_service.insert_event(event)

        # Generate summary (should NOT write to DB)
        summary_service.generate_summary(event)

        # Reload from DB and verify tags are untouched
        reloaded = db_service.get_event(event.id)
        assert reloaded is not None
        assert reloaded.attributes.get("_tags") == ["war", "decisive"]
        assert reloaded.attributes.get("casualties") == 5000

    def test_existing_summary_preserved_when_no_new_generation(
        self, db_service, summary_service
    ):
        """An existing _summary_data must not be wiped by unrelated saves."""
        existing_summary = {
            "text": "Old summary",
            "hash": "abc123",
            "timestamp": 1000.0,
            "model": "old-model",
        }
        entity = Entity(
            name="Wizard",
            type="character",
            description="A wise wizard.",
            attributes={
                "_tags": ["magic"],
                "_summary_data": existing_summary,
            },
        )
        db_service.insert_entity(entity)

        reloaded = db_service.get_entity(entity.id)
        assert reloaded.attributes["_summary_data"] == existing_summary
        assert reloaded.attributes["_tags"] == ["magic"]


class TestEditorSaveMergesAttributes:
    """Simulates the editor save logic to verify attribute merging."""

    @staticmethod
    def _simulate_entity_editor_save(
        hidden_attributes: dict,
        pending_summary_data: dict | None,
        visible_attributes: dict,
        tags: list,
    ) -> dict:
        """Reproduce the entity editor _on_save attribute merge logic.

        This mirrors the fixed logic in EntityEditorWidget._on_save.
        """
        base_attrs = dict(visible_attributes)
        base_attrs["_tags"] = list(tags)

        # Restore hidden attributes first
        for k, v in hidden_attributes.items():
            if k not in base_attrs:
                base_attrs[k] = v

        # Pending summary takes precedence
        if pending_summary_data:
            base_attrs["_summary_data"] = pending_summary_data

        return base_attrs

    @staticmethod
    def _simulate_event_editor_save(
        hidden_attributes: dict,
        pending_summary_data: dict | None,
        visible_attributes: dict,
        tags: list,
    ) -> dict:
        """Reproduce the event editor _on_save attribute merge logic.

        This mirrors the logic in EventEditorWidget._on_save.
        """
        base_attrs = dict(visible_attributes)
        base_attrs["_tags"] = list(tags)

        if pending_summary_data:
            base_attrs["_summary_data"] = pending_summary_data
            for k, v in hidden_attributes.items():
                if k not in base_attrs and k != "_summary_data":
                    base_attrs[k] = v
        else:
            for k, v in hidden_attributes.items():
                if k not in base_attrs:
                    base_attrs[k] = v

        return base_attrs

    def test_entity_save_with_pending_summary_keeps_hidden_attrs(self):
        """When a new summary is pending, hidden attributes must still be merged."""
        hidden = {
            "_tags": ["old_tag"],
            "_summary_data": {"text": "old", "hash": "x", "timestamp": 1.0,
                              "model": "m"},
            "_custom_hidden": "preserve_me",
        }
        pending = {"text": "new", "hash": "y", "timestamp": 2.0, "model": "m2"}

        result = self._simulate_entity_editor_save(
            hidden_attributes=hidden,
            pending_summary_data=pending,
            visible_attributes={"strength": 10},
            tags=["warrior"],
        )

        # Pending summary overwrites old
        assert result["_summary_data"] == pending
        # Tags come from the tag editor, not hidden
        assert result["_tags"] == ["warrior"]
        # Custom hidden attribute must survive
        assert result["_custom_hidden"] == "preserve_me"
        # Visible attribute intact
        assert result["strength"] == 10

    def test_entity_save_without_pending_summary_keeps_existing(self):
        """Without a pending summary, existing _summary_data is restored."""
        old_summary = {"text": "old", "hash": "x", "timestamp": 1.0, "model": "m"}
        hidden = {
            "_tags": ["old"],
            "_summary_data": old_summary,
            "_custom_hidden": "keep",
        }

        result = self._simulate_entity_editor_save(
            hidden_attributes=hidden,
            pending_summary_data=None,
            visible_attributes={"power": 5},
            tags=["mage"],
        )

        assert result["_summary_data"] == old_summary
        assert result["_tags"] == ["mage"]
        assert result["_custom_hidden"] == "keep"
        assert result["power"] == 5

    def test_event_save_with_pending_summary_keeps_hidden_attrs(self):
        """Event editor: pending summary + hidden attributes must coexist."""
        hidden = {
            "_tags": ["old"],
            "_summary_data": {"text": "old", "hash": "x", "timestamp": 1.0,
                              "model": "m"},
            "_event_meta": "important",
        }
        pending = {"text": "new", "hash": "y", "timestamp": 2.0, "model": "m2"}

        result = self._simulate_event_editor_save(
            hidden_attributes=hidden,
            pending_summary_data=pending,
            visible_attributes={"magnitude": 7},
            tags=["natural_disaster"],
        )

        assert result["_summary_data"] == pending
        assert result["_tags"] == ["natural_disaster"]
        assert result["_event_meta"] == "important"
        assert result["magnitude"] == 7

    def test_full_round_trip_entity_summary_persistence(
        self, db_service, summary_service
    ):
        """End-to-end: create → generate summary → simulate save → verify DB."""
        # Step 1: Create entity with tags
        entity = Entity(
            name="Dragon",
            type="creature",
            description="A fearsome dragon.",
            attributes={
                "_tags": ["fire", "flying"],
                "_custom_meta": {"origin": "volcanic"},
                "color": "red",
            },
        )
        db_service.insert_entity(entity)

        # Step 2: Generate summary (returns data, does NOT write to DB)
        summary = summary_service.generate_summary(entity)
        pending = summary.to_dict()

        # Step 3: Simulate editor save (as the fixed entity_editor._on_save does)
        hidden = {
            k: v for k, v in entity.attributes.items() if k.startswith("_")
        }
        visible = {
            k: v for k, v in entity.attributes.items() if not k.startswith("_")
        }
        merged = self._simulate_entity_editor_save(
            hidden_attributes=hidden,
            pending_summary_data=pending,
            visible_attributes=visible,
            tags=["fire", "flying"],
        )

        # Step 4: Persist via DB (as the command layer would)
        entity.attributes = merged
        db_service.insert_entity(entity)

        # Step 5: Verify everything survived
        reloaded = db_service.get_entity(entity.id)
        assert reloaded.attributes["_tags"] == ["fire", "flying"]
        assert reloaded.attributes["_summary_data"]["text"] == "Generated summary text."
        assert reloaded.attributes["_custom_meta"] == {"origin": "volcanic"}
        assert reloaded.attributes["color"] == "red"

    def test_full_round_trip_event_summary_persistence(
        self, db_service, summary_service
    ):
        """End-to-end: create event → generate summary → simulate save → verify DB."""
        event = Event(
            name="Eclipse",
            lore_date=1000.0,
            description="A total solar eclipse.",
            attributes={
                "_tags": ["celestial", "rare"],
                "_custom_meta": {"visibility": "global"},
                "duration_hours": 3,
            },
        )
        db_service.insert_event(event)

        summary = summary_service.generate_summary(event)
        pending = summary.to_dict()

        hidden = {
            k: v for k, v in event.attributes.items() if k.startswith("_")
        }
        visible = {
            k: v for k, v in event.attributes.items() if not k.startswith("_")
        }
        merged = self._simulate_event_editor_save(
            hidden_attributes=hidden,
            pending_summary_data=pending,
            visible_attributes=visible,
            tags=["celestial", "rare"],
        )

        event.attributes = merged
        db_service.insert_event(event)

        reloaded = db_service.get_event(event.id)
        assert reloaded.attributes["_tags"] == ["celestial", "rare"]
        assert reloaded.attributes["_summary_data"]["text"] == "Generated summary text."
        assert reloaded.attributes["_custom_meta"] == {"visibility": "global"}
        assert reloaded.attributes["duration_hours"] == 3
