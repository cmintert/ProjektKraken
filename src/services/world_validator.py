"""World Validator Service.

Scans all entities, events, relations, and tags in a world database and
produces a :class:`WorldValidationReport` describing consistency issues and
completeness scores.
"""

import json
import logging
import math
import time
from collections import Counter
from pathlib import Path
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
from src.core.temporal_window import resolve_temporal_window
from src.services.text_parser import WikiLinkParser

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

    def __init__(self, db_service: Any, *, editorial_checks: bool = True) -> None:
        """Initialise the validator with a database service.

        Args:
            db_service: A connected :class:`~src.services.db_service.DatabaseService`
                instance.
        """
        self.db_service = db_service
        self.editorial_checks = editorial_checks
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
        maps = self.db_service.get_all_maps()

        relation_counts = self._build_relation_count_map(relations)
        attachments = self.db_service.get_attachment_repo().list_all()
        attachment_counts = Counter(attachment.owner_id for attachment in attachments)

        self._check_broken_references(relations, entities, events)
        self._check_duplicate_relations(relations)
        self._check_wikilinks(entities, events)
        self._check_dates(events)
        self._check_temporal_windows(relations, events)
        self._check_attachments(attachments, entities, events)
        self._check_map_assets(maps)
        if self.editorial_checks:
            self._check_orphaned_entities(entities, events, relation_counts)
            self._check_incomplete_data(entities, events)
            self._check_unused_tags(tags, entities, events)
            self._check_completeness_scores(
                entities,
                events,
                relation_counts,
                attachment_counts,
            )

        return self._build_report(entities, events, relations, tags)

    # ------------------------------------------------------------------
    # Private check methods
    # ------------------------------------------------------------------

    def _check_orphaned_entities(
        self,
        entities: list[Entity],
        events: list[Event],
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
        linked_ids = self._resolved_wikilink_targets(entities, events)

        for entity in entities:
            if relation_counts.get(entity.id, 0) > 0:
                continue

            has_legacy_image = bool(entity.attributes.get("_images"))
            if entity.id not in linked_ids and not has_legacy_image:
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
                        # Put the surviving endpoint first for UI navigation.
                        related_ids=[target_id, source_id],
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

    def _check_duplicate_relations(self, relations: list[dict[str, Any]]) -> None:
        """Flag duplicate directed relations with identical endpoints and type."""
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for relation in relations:
            key = (
                str(relation.get("source_id", "")),
                str(relation.get("target_id", "")),
                str(relation.get("rel_type", "")),
            )
            grouped.setdefault(key, []).append(str(relation.get("id", "")))
        for (source_id, target_id, rel_type), relation_ids in grouped.items():
            if len(relation_ids) < 2:
                continue
            for relation_id in relation_ids[1:]:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        issue_type=IssueType.DUPLICATE_RELATION,
                        object_id=relation_id,
                        object_type="relation",
                        object_name=f"Relation {relation_id}",
                        message=(
                            f"Duplicate '{rel_type}' relation from {source_id} "
                            f"to {target_id}."
                        ),
                        suggestion="Review and remove the duplicate relation.",
                        related_ids=[source_id, target_id, *relation_ids],
                        fingerprint=f"duplicate-relation:{source_id}:{target_id}:{rel_type}",
                    )
                )

    def _check_wikilinks(
        self,
        entities: list[Entity],
        events: list[Event],
    ) -> None:
        """Flag missing ID links and missing or ambiguous legacy name links."""
        objects: list[Entity | Event] = [*entities, *events]
        valid_ids = {obj.id for obj in objects}
        ids_by_name: dict[str, list[str]] = {}
        for obj in objects:
            ids_by_name.setdefault(obj.name.casefold(), []).append(obj.id)

        for obj in objects:
            for field_name, text in self._iter_text_fields(obj):
                for link in WikiLinkParser.extract_links(text):
                    if link.is_id_based:
                        if link.target_id in valid_ids:
                            continue
                        target = str(link.target_id or "")
                        issue_type = IssueType.BROKEN_WIKILINK
                        message = f"Wiki link target '{target}' does not exist."
                    else:
                        target = str(link.name or "")
                        matches = ids_by_name.get(target.casefold(), [])
                        if len(matches) == 1:
                            continue
                        issue_type = (
                            IssueType.AMBIGUOUS_WIKILINK
                            if len(matches) > 1
                            else IssueType.BROKEN_WIKILINK
                        )
                        message = (
                            f"Wiki link '{target}' matches multiple objects."
                            if matches
                            else f"Wiki link target '{target}' does not exist."
                        )
                    self.issues.append(
                        ValidationIssue(
                            severity=SeverityLevel.WARNING,
                            issue_type=issue_type,
                            object_id=obj.id,
                            object_type=(
                                "event" if isinstance(obj, Event) else "entity"
                            ),
                            object_name=obj.name,
                            message=message,
                            suggestion="Update the link to an unambiguous ID-based link.",
                            related_ids=[obj.id],
                            fingerprint=(
                                f"wikilink:{obj.id}:{field_name}:{link.span[0]}:{target}"
                            ),
                        )
                    )

    def _check_dates(self, events: list[Event]) -> None:
        """Flag non-finite event dates and negative durations."""
        for event in events:
            if not isinstance(event.lore_date, (int, float)) or not math.isfinite(
                float(event.lore_date)
            ):
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.CRITICAL,
                        issue_type=IssueType.INVALID_DATE,
                        object_id=event.id,
                        object_type="event",
                        object_name=event.name,
                        message="Event has a non-finite lore date.",
                        suggestion="Set a valid lore date.",
                        fingerprint=f"invalid-date:{event.id}",
                    )
                )
            if not isinstance(event.lore_duration, (int, float)) or not math.isfinite(
                float(event.lore_duration)
            ):
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        issue_type=IssueType.INVALID_DURATION,
                        object_id=event.id,
                        object_type="event",
                        object_name=event.name,
                        message="Event duration must be a finite number.",
                        suggestion="Set the duration to zero or a positive value.",
                        fingerprint=f"invalid-duration:{event.id}",
                    )
                )
            elif event.lore_duration < 0:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        issue_type=IssueType.INVALID_DURATION,
                        object_id=event.id,
                        object_type="event",
                        object_name=event.name,
                        message="Event duration cannot be negative.",
                        suggestion="Set the duration to zero or a positive value.",
                        fingerprint=f"invalid-duration:{event.id}",
                    )
                )

    def _check_temporal_windows(
        self,
        relations: list[dict[str, Any]],
        events: list[Event],
    ) -> None:
        """Flag invalid or unresolved dynamic relation windows."""
        event_dates = {
            event.id: float(event.lore_date)
            for event in events
            if isinstance(event.lore_date, (int, float))
            and math.isfinite(float(event.lore_date))
        }
        for relation in relations:
            attrs = relation.get("attributes", {})
            if not any(key.startswith("valid_") for key in attrs):
                continue
            source_date = event_dates.get(str(relation.get("source_id", "")))
            window = resolve_temporal_window(attrs, source_date)
            if window.is_valid:
                continue
            relation_id = str(relation.get("id", ""))
            self.issues.append(
                ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    issue_type=IssueType.INVALID_TEMPORAL_WINDOW,
                    object_id=relation_id,
                    object_type="relation",
                    object_name=f"Relation {relation_id}",
                    message=window.error or "Invalid temporal relation window.",
                    suggestion="Review the relation's temporal settings.",
                    related_ids=[
                        str(relation.get("source_id", "")),
                        str(relation.get("target_id", "")),
                    ],
                    fingerprint=f"invalid-window:{relation_id}",
                )
            )

    def _check_attachments(
        self,
        attachments: list[Any],
        entities: list[Entity],
        events: list[Event],
    ) -> None:
        """Flag orphaned, unsafe, or missing attachment files."""
        valid_ids = {entity.id for entity in entities} | {
            event.id for event in events
        }
        db_path = Path(str(self.db_service.db_path))
        check_files = str(db_path) != ":memory:"
        world_root = db_path.parent.resolve() if check_files else None
        for attachment in attachments:
            if attachment.owner_id not in valid_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.CRITICAL,
                        issue_type=IssueType.ORPHANED_ATTACHMENT,
                        object_id=attachment.id,
                        object_type="attachment",
                        object_name=attachment.id,
                        message="Attachment owner does not exist.",
                        suggestion="Remove or reassign the attachment record.",
                        related_ids=[attachment.owner_id],
                        fingerprint=f"orphaned-attachment:{attachment.id}",
                    )
                )
            if world_root is None:
                continue
            for field_name in ("image_rel_path", "thumb_rel_path"):
                relative_path = getattr(attachment, field_name, None)
                if not relative_path:
                    continue
                resolved = (world_root / relative_path).resolve()
                if not resolved.is_relative_to(world_root):
                    issue_type = IssueType.UNSAFE_ASSET_PATH
                    message = f"Attachment {field_name} escapes the world folder."
                elif not resolved.exists():
                    issue_type = IssueType.MISSING_ASSET
                    message = f"Attachment file is missing: {relative_path}"
                else:
                    continue
                self.issues.append(
                    ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        issue_type=issue_type,
                        object_id=attachment.id,
                        object_type="attachment",
                        object_name=attachment.id,
                        message=message,
                        suggestion="Restore the file or remove the attachment.",
                        related_ids=[attachment.owner_id],
                        fingerprint=f"asset:{attachment.id}:{field_name}",
                    )
                )

    def _check_map_assets(self, maps: list[Any]) -> None:
        """Flag missing or escaping map image paths using world containment."""
        db_path = Path(str(self.db_service.db_path))
        if str(db_path) == ":memory:":
            return
        world_root = db_path.parent.resolve()
        for map_obj in maps:
            relative_path = str(map_obj.image_path or "")
            resolved = (world_root / relative_path).resolve()
            if relative_path and not resolved.is_relative_to(world_root):
                issue_type = IssueType.UNSAFE_ASSET_PATH
                message = "Map image path escapes the world folder."
            elif not relative_path or not resolved.exists():
                issue_type = IssueType.MISSING_ASSET
                message = f"Map image is missing: {relative_path or '(empty path)'}"
            else:
                continue
            self.issues.append(
                ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    issue_type=issue_type,
                    object_id=map_obj.id,
                    object_type="map",
                    object_name=map_obj.name,
                    message=message,
                    suggestion="Restore the map image within the world asset folder.",
                    fingerprint=f"map-asset:{map_obj.id}",
                )
            )

    @staticmethod
    def _iter_text_fields(obj: Entity | Event) -> list[tuple[str, str]]:
        """Return user-authored fields that can contain wikilinks."""
        fields = [("description", obj.description or "")]
        summary = obj.attributes.get("_summary_data")
        if isinstance(summary, dict) and summary.get("text"):
            fields.append(("summary", str(summary["text"])))
        return fields

    def _resolved_wikilink_targets(
        self,
        entities: list[Entity],
        events: list[Event],
    ) -> set[str]:
        """Return unambiguously resolved targets across entity/event text."""
        objects: list[Entity | Event] = [*entities, *events]
        valid_ids = {obj.id for obj in objects}
        ids_by_name: dict[str, list[str]] = {}
        for obj in objects:
            ids_by_name.setdefault(obj.name.casefold(), []).append(obj.id)
        resolved: set[str] = set()
        for obj in objects:
            for _field_name, text in self._iter_text_fields(obj):
                for link in WikiLinkParser.extract_links(text):
                    if link.is_id_based and link.target_id in valid_ids:
                        resolved.add(str(link.target_id))
                    elif not link.is_id_based:
                        matches = ids_by_name.get(str(link.name or "").casefold(), [])
                        if len(matches) == 1:
                            resolved.add(matches[0])
        return resolved

    def _check_completeness_scores(
        self,
        entities: list[Entity],
        events: list[Event],
        relation_counts: dict[str, int],
        attachment_counts: Counter[str],
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
                has_description=bool((entity.description or "").strip()),
                description_length=len((entity.description or "").strip()),
                has_image=(
                    attachment_counts[entity.id] > 0
                    or bool(entity.attributes.get("_images"))
                ),
                has_tags=bool(entity.attributes.get("_tags")),
                tag_count=len(entity.attributes.get("_tags", [])),
                relation_count=relation_counts.get(entity.id, 0),
                completeness_score=0.0,
                has_name=bool(entity.name.strip()),
                has_type=bool(entity.type.strip()),
            )
            score.completeness_score = score.calculate_score()
            self.completeness_scores.append(score)

        for event in events:
            score = CompletenessScore(
                object_id=event.id,
                object_type="event",
                name=event.name,
                has_description=bool((event.description or "").strip()),
                description_length=len((event.description or "").strip()),
                has_image=(
                    attachment_counts[event.id] > 0
                    or bool(event.attributes.get("_images"))
                ),
                has_tags=bool(event.attributes.get("_tags")),
                tag_count=len(event.attributes.get("_tags", [])),
                relation_count=relation_counts.get(event.id, 0),
                completeness_score=0.0,
                has_name=bool(event.name.strip()),
                has_type=bool(event.type.strip()),
                has_valid_date=(
                    isinstance(event.lore_date, (int, float))
                    and math.isfinite(float(event.lore_date))
                ),
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
