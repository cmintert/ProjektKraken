"""Tests for WorldValidator service."""

import time
import uuid

import pytest

from src.core.analysis import IssueType, SeverityLevel, WorldValidationReport
from src.core.entities import Entity
from src.core.events import Event
from src.services.world_validator import WorldValidator


def insert_corrupt_relation(db_service, source_id: str, target_id: str) -> None:
    """Insert a legacy-invalid row to exercise repair diagnostics."""
    connection = db_service.get_connection()
    connection.execute("DROP TRIGGER IF EXISTS validate_relation_endpoints_insert")
    connection.execute("DROP TRIGGER IF EXISTS validate_relation_endpoints_update")
    connection.execute(
        """
        INSERT INTO relations (
            id, source_id, target_id, rel_type, attributes, created_at
        ) VALUES (?, ?, ?, 'test', '{}', ?)
        """,
        (str(uuid.uuid4()), source_id, target_id, time.time()),
    )
    connection.commit()


@pytest.fixture
def validator(db_service):
    """WorldValidator wired to a fresh in-memory database."""
    return WorldValidator(db_service)


@pytest.fixture
def populated_db(db_service):
    """Database with a mix of entities, events, and relations for integration tests."""
    # Entities
    e1 = Entity(
        name="Gandalf", type="character",
        description="A wise wizard with a long history.",
    )
    e2 = Entity(
        name="Mordor", type="location",
        description="The dark land of shadow and flame.",
    )
    e3 = Entity(id="e3", name="Ring", type="artifact", description="")
    db_service.insert_entity(e1)
    db_service.insert_entity(e2)
    db_service.insert_entity(e3)

    # Events
    ev1 = Event(
        name="Battle of Helm's Deep", lore_date=100.0,
        description="A major battle in the war.",
    )
    ev2 = Event(id="ev2", name="X", lore_date=200.0, description="")
    db_service.insert_event(ev1)
    db_service.insert_event(ev2)

    # Relation between e1 and e2
    db_service.insert_relation(e1.id, e2.id, "located_in", {})

    return db_service


@pytest.mark.unit
class TestCheckOrphanedEntities:
    def test_entity_with_no_relations_is_flagged(self, db_service, validator):
        entity = Entity(id="e1", name="Isolated", type="character", description="No connections.")
        db_service.insert_entity(entity)

        report = validator.validate()

        orphaned = report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        assert len(orphaned) == 1
        assert orphaned[0].object_id == "e1"
        assert orphaned[0].severity == SeverityLevel.WARNING

    def test_entity_with_relation_is_not_flagged(self, db_service, validator):
        e1 = Entity(name="Frodo", type="character", description="The ring-bearer.")
        e2 = Entity(name="Mordor", type="location", description="The dark land.")
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_relation(e1.id, e2.id, "traveled_to", {})

        report = validator.validate()

        orphaned = report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        assert len(orphaned) == 0

    def test_entity_as_relation_target_is_not_flagged(self, db_service, validator):
        e1 = Entity(name="Source", type="character", description="Has a relation.")
        e2 = Entity(name="Target", type="location", description="Is a target.")
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_relation(e1.id, e2.id, "located_in", {})

        report = validator.validate()

        orphaned = report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        assert len(orphaned) == 0


@pytest.mark.unit
class TestCheckBrokenReferences:
    def test_relation_with_missing_source_is_flagged_critical(self, db_service, validator):
        e2 = Entity(name="Target", type="location", description="Exists.")
        db_service.insert_entity(e2)
        ghost_source = str(uuid.uuid4())
        insert_corrupt_relation(db_service, ghost_source, e2.id)

        report = validator.validate()

        broken = report.get_issues_by_type(IssueType.BROKEN_REFERENCE)
        assert len(broken) == 1
        assert broken[0].severity == SeverityLevel.CRITICAL
        assert ghost_source in broken[0].message

    def test_relation_with_missing_target_is_flagged_critical(self, db_service, validator):
        e1 = Entity(name="Source", type="character", description="Exists.")
        db_service.insert_entity(e1)
        ghost_target = str(uuid.uuid4())
        insert_corrupt_relation(db_service, e1.id, ghost_target)

        report = validator.validate()

        broken = report.get_issues_by_type(IssueType.BROKEN_REFERENCE)
        assert len(broken) == 1
        assert broken[0].severity == SeverityLevel.CRITICAL
        assert ghost_target in broken[0].message

    def test_valid_entity_to_entity_relation_not_flagged(self, db_service, validator):
        e1 = Entity(name="A", type="character", description="Valid entity.")
        e2 = Entity(name="B", type="location", description="Also valid.")
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_relation(e1.id, e2.id, "related_to", {})

        report = validator.validate()

        assert len(report.get_issues_by_type(IssueType.BROKEN_REFERENCE)) == 0

    def test_valid_entity_to_event_relation_not_flagged(self, db_service, validator):
        e1 = Entity(name="Hero", type="character", description="Present at battle.")
        ev1 = Event(name="Battle", lore_date=100.0, description="The big fight.")
        db_service.insert_entity(e1)
        db_service.insert_event(ev1)
        db_service.insert_relation(e1.id, ev1.id, "participated_in", {})

        report = validator.validate()

        assert len(report.get_issues_by_type(IssueType.BROKEN_REFERENCE)) == 0


@pytest.mark.unit
class TestCheckIncompleteData:
    def test_entity_with_short_description_flagged_info(self, db_service, validator):
        entity = Entity(id="e1", name="Stub", type="character", description="Hi.")
        db_service.insert_entity(entity)

        report = validator.validate()

        incomplete = report.get_issues_by_type(IssueType.INCOMPLETE_ENTITY)
        assert len(incomplete) == 1
        assert incomplete[0].severity == SeverityLevel.INFO

    def test_entity_with_adequate_description_not_flagged(self, db_service, validator):
        entity = Entity(
            id="e1",
            name="Detailed",
            type="character",
            description="This entity has a very well-developed backstory and history.",
        )
        db_service.insert_entity(entity)

        report = validator.validate()

        assert len(report.get_issues_by_type(IssueType.INCOMPLETE_ENTITY)) == 0

    def test_entity_with_no_description_flagged(self, db_service, validator):
        entity = Entity(id="e1", name="Empty", type="character", description="")
        db_service.insert_entity(entity)

        report = validator.validate()

        assert len(report.get_issues_by_type(IssueType.INCOMPLETE_ENTITY)) == 1

    def test_event_with_short_description_flagged_info(self, db_service, validator):
        event = Event(id="ev1", name="Thing happened", lore_date=100.0, description="Short.")
        db_service.insert_event(event)

        report = validator.validate()

        incomplete = report.get_issues_by_type(IssueType.INCOMPLETE_EVENT)
        assert len(incomplete) == 1
        assert incomplete[0].severity == SeverityLevel.INFO

    def test_event_with_adequate_description_not_flagged(self, db_service, validator):
        event = Event(
            id="ev1",
            name="Battle",
            lore_date=100.0,
            description="This was a decisive engagement that changed the course of the war.",
        )
        db_service.insert_event(event)

        report = validator.validate()

        assert len(report.get_issues_by_type(IssueType.INCOMPLETE_EVENT)) == 0


@pytest.mark.unit
class TestCheckUnusedTags:
    def test_tag_used_once_is_flagged_info(self, db_service, validator):
        db_service.create_tag("rare-tag")
        entity = Entity(
            id="e1",
            name="OnlyUser",
            type="character",
            description="Uses the tag.",
            attributes={"_tags": ["rare-tag"]},
        )
        db_service.insert_entity(entity)

        report = validator.validate()

        unused = report.get_issues_by_type(IssueType.TAG_UNUSED)
        tag_names = [i.object_name for i in unused]
        assert "rare-tag" in tag_names
        assert unused[0].severity == SeverityLevel.INFO

    def test_tag_used_twice_is_not_flagged(self, db_service, validator):
        db_service.create_tag("common-tag")
        e1 = Entity(
            id="e1",
            name="User1",
            type="character",
            description="First user.",
            attributes={"_tags": ["common-tag"]},
        )
        e2 = Entity(
            id="e2",
            name="User2",
            type="character",
            description="Second user.",
            attributes={"_tags": ["common-tag"]},
        )
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)

        report = validator.validate()

        unused = report.get_issues_by_type(IssueType.TAG_UNUSED)
        tag_names = [i.object_name for i in unused]
        assert "common-tag" not in tag_names

    def test_tag_not_used_at_all_is_flagged(self, db_service, validator):
        db_service.create_tag("unused-tag")

        report = validator.validate()

        unused = report.get_issues_by_type(IssueType.TAG_UNUSED)
        assert any(i.object_name == "unused-tag" for i in unused)


@pytest.mark.unit
class TestCheckCompletenessScores:
    def test_scores_generated_for_all_entities_and_events(self, db_service, validator):
        e1 = Entity(id="e1", name="A", type="character", description="")
        e2 = Entity(id="e2", name="B", type="location", description="")
        ev1 = Event(id="ev1", name="C", lore_date=100.0, description="")
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)

        report = validator.validate()

        assert len(report.completeness_scores) == 3

    def test_empty_db_produces_zero_scores(self, db_service, validator):
        report = validator.validate()

        assert len(report.completeness_scores) == 0


@pytest.mark.unit
class TestValidateReport:
    def test_empty_db_returns_valid_report(self, db_service, validator):
        report = validator.validate()

        assert isinstance(report, WorldValidationReport)
        assert report.total_entities == 0
        assert report.total_events == 0
        assert report.total_relations == 0
        assert report.issues == []

    def test_report_totals_are_accurate(self, populated_db, validator):
        report = validator.validate()

        assert report.total_entities == 3
        assert report.total_events == 2
        assert report.total_relations == 1

    def test_report_timestamp_is_recent(self, db_service, validator):
        before = time.time()
        report = validator.validate()
        after = time.time()

        assert before <= report.timestamp <= after

    def test_issues_by_severity_counts_are_correct(self, db_service, validator):
        # Insert one entity that will generate a BROKEN_REFERENCE (CRITICAL)
        insert_corrupt_relation(
            db_service, str(uuid.uuid4()), str(uuid.uuid4())
        )

        report = validator.validate()

        assert report.issues_by_severity.get(SeverityLevel.CRITICAL, 0) >= 1

    def test_orphaned_entities_count_matches_issues(self, db_service, validator):
        entity = Entity(id="e1", name="Orphan", type="character", description="No connections.")
        db_service.insert_entity(entity)

        report = validator.validate()

        assert report.orphaned_entities_count == len(
            report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        )

    def test_broken_references_count_matches_issues(self, db_service, validator):
        insert_corrupt_relation(
            db_service, str(uuid.uuid4()), str(uuid.uuid4())
        )

        report = validator.validate()

        assert report.broken_references_count == len(
            report.get_issues_by_type(IssueType.BROKEN_REFERENCE)
        )

    def test_doubly_broken_relation_produces_two_issues(self, db_service, validator):
        """A relation with both source and target missing yields 2 broken-ref issues."""
        insert_corrupt_relation(
            db_service, str(uuid.uuid4()), str(uuid.uuid4())
        )

        report = validator.validate()

        broken = report.get_issues_by_type(IssueType.BROKEN_REFERENCE)
        assert len(broken) == 2

    def test_completeness_score_field_is_populated(self, db_service, validator):
        """completeness_score on each CompletenessScore is set to calculate_score() value."""
        entity = Entity(
            id="e1", name="Detailed", type="character",
            description="A very long and detailed description here.",
        )
        db_service.insert_entity(entity)

        report = validator.validate()

        assert len(report.completeness_scores) == 1
        cs = report.completeness_scores[0]
        assert cs.completeness_score == cs.calculate_score()
        assert cs.completeness_score > 0


@pytest.mark.unit
class TestOrphanEdgeCases:
    def test_entity_excluded_from_orphan_if_mentioned_in_attributes(
        self, db_service, validator
    ):
        """Entity is not orphaned if its ID appears in another entity's attributes."""
        e1 = Entity(id="e1", name="Referenced", type="character", description="")
        e2 = Entity(
            id="e2",
            name="Referencer",
            type="character",
            description="",
            attributes={"linked_to": "e1"},  # e1's ID embedded in e2's attrs
        )
        db_service.insert_entity(e1)
        db_service.insert_entity(e2)

        report = validator.validate()

        orphaned_ids = [i.object_id for i in report.get_issues_by_type(IssueType.ORPHANED_ENTITY)]
        assert "e1" not in orphaned_ids

    def test_entity_with_image_not_flagged_as_orphan(self, db_service, validator):
        """Entity with an image attachment is excluded from orphan detection."""
        entity = Entity(
            id="e1",
            name="Pictured",
            type="character",
            description="",
            attributes={"_images": ["some-image-id"]},
        )
        db_service.insert_entity(entity)

        report = validator.validate()

        orphaned_ids = [i.object_id for i in report.get_issues_by_type(IssueType.ORPHANED_ENTITY)]
        assert "e1" not in orphaned_ids


@pytest.mark.unit
def test_get_all_relations_on_db_service(db_service):
    """Smoke test: get_all_relations() was added to DatabaseService."""
    result = db_service.get_all_relations()
    assert isinstance(result, list)
