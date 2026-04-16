"""World Validator Service.

Scans all entities, events, relations, and tags in a world database and
produces a :class:`WorldValidationReport` describing consistency issues and
completeness scores.
"""

import json
import logging
import time
from collections import Counter
from typing import Any

from src.core.analysis import (
    CompletenessScore,
    IssueType,
    SeverityLevel,
    ValidationIssue,
    WorldValidationReport,
)
from src.core.entities import Entity
from src.core.events import Event

logger = logging.getLogger(__name__)

_MIN_DESCRIPTION_LENGTH: int = 20
_MIN_TAG_USAGE_COUNT: int = 2


class WorldValidator:
    """Validates world consistency and completeness.

    Runs a suite of checks against a world database via
    :class:`~src.services.db_service.DatabaseService` and returns a
    :class:`~src.core.analysis.WorldValidationReport`.

    Attributes:
        db_service: The database service used to fetch world data.
        issues: Accumulated issues from the last ``validate()`` call.
        completeness_scores: Accumulated scores from the last ``validate()`` call.
    """

    def __init__(self, db_service: Any) -> None:
        """Initialise the validator with a database service.

        Args:
            db_service: A connected :class:`~src.services.db_service.DatabaseService`
                instance.
        """
        self.db_service = db_service
        self.issues: list[ValidationIssue] = []
        self.completeness_scores: list[CompletenessScore] = []

    def validate(self) -> WorldValidationReport:
        """Run the full validation suite and return a report.

        Clears any previously accumulated issues and scores before running.

        Returns:
            WorldValidationReport: A complete report for the current world state.
        """
        self.issues = []
        self.completeness_scores = []

        entities: list[Entity] = self.db_service.get_all_entities()
        events: list[Event] = self.db_service.get_all_events()
        relations: list[dict[str, Any]] = self.db_service.get_all_relations()
        tags: list[dict[str, Any]] = self.db_service.get_all_tags()

        relation_counts = self._build_relation_count_map(relations)

        self._check_orphaned_entities(entities, relation_counts)
        self._check_broken_references(relations, entities, events)
        self._check_incomplete_data(entities, events)
        self._check_unused_tags(tags, entities, events)
        self._check_completeness_scores(entities, events, relation_counts)

        return self._build_report(entities, events, relations, tags)

    # ------------------------------------------------------------------
    # Private check methods
    # ------------------------------------------------------------------

    def _check_orphaned_entities(
        self,
        entities: list[Entity],
        relation_counts: dict[str, int],
    ) -> None:
        """Flag entities that have no relations and are not mentioned elsewhere.

        An entity is considered orphaned when it has zero outgoing or incoming
        relations, is not referenced in any other entity's attributes JSON, and
        has no image attachment.

        Args:
            entities: All entities in the world.
            relation_counts: Mapping of object_id → total relation count,
                as returned by :meth:`_build_relation_count_map`.
        """
        # Pre-serialise each entity's attributes once so the O(E²) mention
        # scan reuses the cached strings instead of re-calling json.dumps per pair.
        attrs_json: dict[str, str] = {
            e.id: json.dumps(e.attributes, default=str) for e in entities
        }

        for entity in entities:
            if relation_counts.get(entity.id, 0) > 0:
                continue

            mentioned = any(
                entity.id in attrs_json[e.id]
                for e in entities
                if e.id != entity.id
            )

            has_image = bool(entity.attributes.get("_images"))

            if not mentioned and not has_image:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        issue_type=IssueType.ORPHANED_ENTITY,
                        object_id=entity.id,
                        object_type="entity",
                        object_name=entity.name,
                        message=(
                            f"Entity '{entity.name}' has no relations and is not"
                            " mentioned elsewhere."
                        ),
                        suggestion=(
                            "Consider connecting this entity to others or removing"
                            " it if no longer needed."
                        ),
                        related_ids=[],
                    )
                )

    def _check_broken_references(
        self,
        relations: list[dict[str, Any]],
        entities: list[Entity],
        events: list[Event],
    ) -> None:
        """Flag relations whose source or target does not exist.

        Args:
            relations: All relations as raw dicts.
            entities: All entities in the world.
            events: All events in the world.
        """
        entity_ids = {e.id for e in entities}
        event_ids = {e.id for e in events}
        valid_ids = entity_ids | event_ids

        for relation in relations:
            rel_id = relation.get("id", "")
            source_id = relation.get("source_id", "")
            target_id = relation.get("target_id", "")

            if source_id not in valid_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.CRITICAL,
                        issue_type=IssueType.BROKEN_REFERENCE,
                        object_id=rel_id,
                        object_type="relation",
                        object_name=f"Relation {rel_id}",
                        message=f"Relation source '{source_id}' does not exist.",
                        suggestion="Delete this relation or update its source.",
                        related_ids=[source_id, target_id],
                    )
                )

            if target_id not in valid_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.CRITICAL,
                        issue_type=IssueType.BROKEN_REFERENCE,
                        object_id=rel_id,
                        object_type="relation",
                        object_name=f"Relation {rel_id}",
                        message=f"Relation target '{target_id}' does not exist.",
                        suggestion="Delete this relation or update its target.",
                        related_ids=[source_id, target_id],
                    )
                )

    def _check_incomplete_data(
        self,
        entities: list[Entity],
        events: list[Event],
    ) -> None:
        """Flag entities and events with very short or empty descriptions.

        The minimum useful description length is ``_MIN_DESCRIPTION_LENGTH``
        characters (currently 20).

        Args:
            entities: All entities in the world.
            events: All events in the world.
        """
        for entity in entities:
            self._flag_if_incomplete(
                obj_id=entity.id,
                obj_type="entity",
                obj_name=entity.name,
                description=entity.description or "",
                issue_type=IssueType.INCOMPLETE_ENTITY,
                suggestion="Add more details to flesh out this character/location/artifact.",
            )

        for event in events:
            self._flag_if_incomplete(
                obj_id=event.id,
                obj_type="event",
                obj_name=event.name,
                description=event.description or "",
                issue_type=IssueType.INCOMPLETE_EVENT,
                suggestion="Add more context and details.",
            )

    def _check_unused_tags(
        self,
        tags: list[dict[str, Any]],
        entities: list[Entity],
        events: list[Event],
    ) -> None:
        """Flag tags that are used in fewer than ``_MIN_TAG_USAGE_COUNT`` items.

        Tags come from the tags table as dicts with at least a ``name`` key.
        Usage is counted from entity and event ``attributes["_tags"]`` lists.

        Args:
            tags: All tags from the database (as dicts with a ``name`` key).
            entities: All entities in the world.
            events: All events in the world.
        """
        tag_usage: dict[str, int] = {}

        for entity in entities:
            for tag_name in entity.attributes.get("_tags", []):
                tag_usage[tag_name] = tag_usage.get(tag_name, 0) + 1

        for event in events:
            for tag_name in event.attributes.get("_tags", []):
                tag_usage[tag_name] = tag_usage.get(tag_name, 0) + 1

        for tag in tags:
            tag_name = tag["name"]
            if tag_usage.get(tag_name, 0) < _MIN_TAG_USAGE_COUNT:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.INFO,
                        issue_type=IssueType.TAG_UNUSED,
                        object_id=tag_name,
                        object_type="tag",
                        object_name=tag_name,
                        message=(
                            f"Tag '{tag_name}' is used in fewer than"
                            f" {_MIN_TAG_USAGE_COUNT} items."
                        ),
                        suggestion=(
                            "Consider consolidating tags or removing if no longer"
                            " relevant."
                        ),
                        related_ids=[],
                    )
                )

    def _check_completeness_scores(
        self,
        entities: list[Entity],
        events: list[Event],
        relation_counts: dict[str, int],
    ) -> None:
        """Compute a completeness score for each entity and event.

        Populates ``self.completeness_scores`` with one entry per object.
        The ``completeness_score`` field on each entry is set to the live
        computed value via :meth:`~src.core.analysis.CompletenessScore.calculate_score`.

        Args:
            entities: All entities in the world.
            events: All events in the world.
            relation_counts: Mapping of object_id → total relation count,
                as returned by :meth:`_build_relation_count_map`.
        """
        for entity in entities:
            score = CompletenessScore(
                object_id=entity.id,
                object_type="entity",
                name=entity.name,
                has_description=bool(entity.description),
                description_length=len(entity.description or ""),
                has_image=bool(entity.attributes.get("_images")),
                has_tags=bool(entity.attributes.get("_tags")),
                tag_count=len(entity.attributes.get("_tags", [])),
                relation_count=relation_counts.get(entity.id, 0),
                completeness_score=0.0,
            )
            score.completeness_score = score.calculate_score()
            self.completeness_scores.append(score)

        for event in events:
            score = CompletenessScore(
                object_id=event.id,
                object_type="event",
                name=event.name,
                has_description=bool(event.description),
                description_length=len(event.description or ""),
                has_image=bool(event.attributes.get("_images")),
                has_tags=bool(event.attributes.get("_tags")),
                tag_count=len(event.attributes.get("_tags", [])),
                relation_count=relation_counts.get(event.id, 0),
                completeness_score=0.0,
            )
            score.completeness_score = score.calculate_score()
            self.completeness_scores.append(score)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_relation_count_map(
        self, relations: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Build a mapping of object ID → total relation count in O(R) time.

        Each relation contributes one count to its source and one to its target.

        Args:
            relations: All relations as raw dicts with ``source_id``/``target_id`` keys.

        Returns:
            dict[str, int]: Mapping of object_id → number of relations.
        """
        counts: dict[str, int] = {}
        for r in relations:
            for key in ("source_id", "target_id"):
                obj_id = r.get(key)
                if obj_id:
                    counts[obj_id] = counts.get(obj_id, 0) + 1
        return counts

    def _flag_if_incomplete(
        self,
        obj_id: str,
        obj_type: str,
        obj_name: str,
        description: str,
        issue_type: IssueType,
        suggestion: str,
    ) -> None:
        """Append an incomplete-data issue if description is too short.

        Args:
            obj_id: The object's unique identifier.
            obj_type: One of "entity" or "event".
            obj_name: Human-readable display name.
            description: The raw description text.
            issue_type: The issue type to use (INCOMPLETE_ENTITY or INCOMPLETE_EVENT).
            suggestion: Actionable fix suggestion.
        """
        if len(description.strip()) < _MIN_DESCRIPTION_LENGTH:
            self.issues.append(
                ValidationIssue(
                    severity=SeverityLevel.INFO,
                    issue_type=issue_type,
                    object_id=obj_id,
                    object_type=obj_type,
                    object_name=obj_name,
                    message=f"{obj_type.capitalize()} '{obj_name}' has minimal description.",
                    suggestion=suggestion,
                    related_ids=[],
                )
            )

    def _is_mentioned_in(self, entity_id: str, other_entity: Entity) -> bool:
        """Return True if entity_id appears anywhere in other_entity's attributes.

        Uses JSON serialization to catch references stored anywhere in the
        flexible attributes dict.

        Args:
            entity_id: The ID to search for.
            other_entity: The entity whose attributes are searched.

        Returns:
            bool: True if entity_id is found in the serialized attributes.
        """
        attrs_json = json.dumps(other_entity.attributes, default=str)
        return entity_id in attrs_json

    def _build_report(
        self,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
        tags: list[dict[str, Any]],
    ) -> WorldValidationReport:
        """Construct and return the final WorldValidationReport.

        Args:
            entities: All entities in the world.
            events: All events in the world.
            relations: All relations as raw dicts.
            tags: All tags as raw dicts.

        Returns:
            WorldValidationReport: The completed report.
        """
        # Single pass over issues to build all counts simultaneously.
        severity_counts: Counter[SeverityLevel] = Counter(
            i.severity for i in self.issues
        )
        type_counts: Counter[IssueType] = Counter(i.issue_type for i in self.issues)

        issues_by_severity: dict[SeverityLevel, int] = {
            SeverityLevel.CRITICAL: severity_counts[SeverityLevel.CRITICAL],
            SeverityLevel.WARNING: severity_counts[SeverityLevel.WARNING],
            SeverityLevel.INFO: severity_counts[SeverityLevel.INFO],
        }
        issues_by_type: dict[str, int] = {
            it.value: cnt for it, cnt in type_counts.items() if cnt > 0
        }

        avg_completeness = (
            sum(s.completeness_score for s in self.completeness_scores)
            / len(self.completeness_scores)
            if self.completeness_scores
            else 0.0
        )

        return WorldValidationReport(
            timestamp=time.time(),
            total_entities=len(entities),
            total_events=len(events),
            total_relations=len(relations),
            total_tags=len(tags),
            issues=self.issues,
            issues_by_severity=issues_by_severity,
            issues_by_type=issues_by_type,
            completeness_scores=self.completeness_scores,
            average_completeness=avg_completeness,
            orphaned_entities_count=type_counts[IssueType.ORPHANED_ENTITY],
            broken_references_count=type_counts[IssueType.BROKEN_REFERENCE],
            unused_tags_count=type_counts[IssueType.TAG_UNUSED],
        )
