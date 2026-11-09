"""Temporal Analyzer Service.

Scans all events, entities, and relations in a world database and produces a
:class:`~src.core.analysis.TemporalAnalysisReport` describing timeline gaps,
temporal conflicts, and character lifespan data.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from src.core.analysis import (
    CharacterLifespan,
    SeverityLevel,
    TemporalAnalysisReport,
    TemporalConflict,
    TimelineGap,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.lifecycle import (
    LivingClaim,
    character_claims,
    competing_claims,
    definitely_outside_life,
)
from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_window import resolve_temporal_window
from src.services.text_parser import WikiLinkParser

if TYPE_CHECKING:
    from src.core.date_parser import DateParser
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

_GAP_THRESHOLD: float = 365.0 * 100.0  # 100 Gregorian years in days
_MIN_GAP_EVENT_COUNT = 2


class TemporalAnalyzer:
    """Analyzes temporal consistency and gaps in a world database.

    Runs three checks against the database via
    :class:`~src.services.db_service.DatabaseService`:

    - **Timeline gaps**: consecutive event pairs separated by more than
      :attr:`gap_threshold` lore-time units.
    - **Temporal conflicts**: relations whose ``valid_from``/``valid_to``
      attribute window is logically invalid (``valid_from >= valid_to``).
    - **Character lifespans**: per-entity birth/death tracking derived from
      relations with explicit ``birth`` or ``death`` keys, plus
      any events that fall outside the computed lifespan.

    Attributes:
        db_service: The database service used to fetch world data.
        gap_threshold: Minimum lore-time gap duration to flag (default 100.0).
    """

    def __init__(self, db_service: "DatabaseService | None" = None) -> None:
        """Initialise the analyzer with a database service.

        Args:
            db_service: An optional connected
                :class:`~src.services.db_service.DatabaseService` instance.
        """
        self.db_service = db_service
        self.gap_threshold: float = _GAP_THRESHOLD
        self._date_parser: DateParser | None = None
        self._year_length: float = 365.0

    def analyze(self) -> TemporalAnalysisReport:
        """Run the full temporal analysis suite and return a report.

        Returns:
            TemporalAnalysisReport: A complete temporal analysis report.
        """
        if self.db_service is None:
            raise RuntimeError("DatabaseService is required for analyze()")

        events: list[Event] = self.db_service.get_all_events()
        entities: list[Entity] = self.db_service.get_all_entities()
        relations: list[dict[str, Any]] = self.db_service.get_all_relations()
        calendar_config = self.db_service.get_active_calendar_config()
        return self.analyze_data(
            entities=entities,
            events=events,
            relations=relations,
            calendar_config=calendar_config,
        )

    def analyze_data(
        self,
        *,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
        calendar_config: Any | None,
    ) -> TemporalAnalysisReport:
        """Analyze an immutable, database-independent world snapshot.

        Args:
            entities: Entity snapshot reconstructed from serialized data.
            events: Event snapshot reconstructed from serialized data.
            relations: Copied relation dictionaries.
            calendar_config: Active calendar configuration, or ``None``.

        Returns:
            TemporalAnalysisReport: A complete temporal analysis report.
        """
        cal = calendar_config
        using_default = False
        if cal is None:
            from src.core.calendar import CalendarConfig

            cal = CalendarConfig.create_default()
            using_default = True
            logger.debug(
                "TemporalAnalyzer: no active calendar found; falling back to Gregorian"
            )

        calendar_name = f"{cal.name} (default)" if using_default else cal.name
        from src.core.date_parser import DateParser

        self._date_parser = DateParser(cal)
        self._year_length = float(cal.get_year_length(1))
        self.gap_threshold = self._year_length * 100.0  # flag gaps > 100 lore-years

        gaps, dated = self._detect_timeline_gaps(events)
        conflicts = self._detect_temporal_conflicts(relations, events)
        conflicts.extend(self._detect_constraint_conflicts(events))
        from src.services.temporal_conflict_service import exclusive_role_conflicts

        conflicts.extend(
            exclusive_role_conflicts(relations, events, self._date_parser.converter)
        )

        lifespans, lifespan_conflicts = self._analyze_character_lifespans(
            entities,
            events,
            relations,
        )
        conflicts.extend(lifespan_conflicts)

        # dated is already sorted; extract min/max without a second coercion pass.
        earliest = dated[0][0] if dated else None
        latest = dated[-1][0] if dated else None

        return TemporalAnalysisReport(
            timestamp=time.time(),
            timeline_gaps=gaps,
            total_gap_duration=sum(g.gap_duration for g in gaps),
            conflicts=conflicts,
            character_lifespans=lifespans,
            earliest_event_date=earliest,
            latest_event_date=latest,
            calendar_name=calendar_name,
            calendar_config=cal,
        )

    # ------------------------------------------------------------------
    # Private analysis methods
    # ------------------------------------------------------------------

    def _detect_timeline_gaps(
        self, events: list[Event]
    ) -> tuple[list[TimelineGap], list[tuple[float, Event]]]:
        """Detect consecutive event pairs with a gap exceeding the threshold.

        Events are sorted by ``lore_date`` before comparison, so insertion
        order does not matter.  Events whose ``lore_date`` cannot be coerced
        to a float are silently skipped.

        Args:
            events: All events in the world.

        Returns:
            tuple: ``(gaps, dated)`` where *gaps* is a list of
            :class:`~src.core.analysis.TimelineGap` objects sorted ascending
            by start date, and *dated* is the sorted
            ``list[tuple[float, Event]]`` used internally — callers can
            extract ``min``/``max`` dates from it without a second coercion
            pass.
        """
        dated: list[tuple[float, Event]] = []
        for event in events:
            date = self._coerce_date(event.lore_date)
            if date is not None:
                dated.append((date, event))

        if len(dated) < _MIN_GAP_EVENT_COUNT:
            return [], dated

        dated.sort(key=lambda x: x[0])
        gaps: list[TimelineGap] = []

        for (date_a, ev_a), (date_b, ev_b) in zip(dated, dated[1:]):
            from src.core.temporal_anchors import resolve_event_anchors

            bounds = resolve_event_anchors(
                [ev_a, ev_b], self._date_parser.converter if self._date_parser else None
            )
            end_a, start_b = (
                bounds[f"event:{ev_a.id}"].hard_end,
                bounds[f"event:{ev_b.id}"].hard_start,
            )
            if end_a is None or start_b is None:
                continue
            duration = start_b - end_a
            if duration > self.gap_threshold:
                duration_years = duration / self._year_length
                gaps.append(
                    TimelineGap(
                        start_date=date_a,
                        end_date=date_b,
                        gap_duration=duration,
                        message=(
                            f"Gap of {duration_years:.0f} years between"
                            f" '{ev_a.name}' and '{ev_b.name}'"
                        ),
                    )
                )

        return gaps, dated

    def _detect_constraint_conflicts(
        self, events: list[Event]
    ) -> list[TemporalConflict]:
        """Report impossible chronology independently of reduced date precision."""
        from src.core.event_timing.solver import resolve_world
        from src.core.temporal_anchors import resolve_event_anchors
        from src.core.temporal_constraints import (
            TemporalConstraint,
            validate_constraints,
        )

        constraints: list[TemporalConstraint] = []
        for event in events:
            constraints.extend(
                TemporalConstraint.from_dict(item)
                for item in event.attributes.get("_temporal_v2", {}).get(
                    "constraints", []
                )
            )
        anchors = resolve_event_anchors(
            events, self._date_parser.converter if self._date_parser else None
        )
        messages = [
            *validate_constraints(constraints, anchors),
            *(
                issue.message
                for issue in resolve_world(
                    events, self._date_parser.converter if self._date_parser else None
                ).issues
                if issue.code == "infeasible"
            ),
        ]
        return [
            TemporalConflict(
                conflict_type="chronological_constraint",
                entity_id="",
                entity_name="Chronology",
                problem_date=None,
                message=message,
                suggestion="Review the event ordering assertions.",
                severity=SeverityLevel.CRITICAL,
                related_ids=[],
                fingerprint=f"chronology:{message}",
            )
            for message in dict.fromkeys(messages)
        ]

    def _detect_temporal_conflicts(
        self,
        relations: list[dict[str, Any]],
        events: list[Event] | None = None,
    ) -> list[TemporalConflict]:
        """Flag relations whose ``valid_from``/``valid_to`` window is invalid.

        A window is considered invalid when both attributes are numeric and
        ``valid_from >= valid_to``.

        Args:
            relations: All relations as raw dicts with ``attributes`` sub-dict.

        Returns:
            list[TemporalConflict]: All detected window conflicts.
        """
        conflicts: list[TemporalConflict] = []

        from src.core.temporal_anchors import resolve_event_anchors

        event_map = {event.id: event for event in events or []}
        anchors = resolve_event_anchors(
            events or [], self._date_parser.converter if self._date_parser else None
        )
        for rel in relations:
            attrs = rel.get("attributes", {})
            if not any(
                key in attrs
                for key in (
                    "valid_from",
                    "valid_to",
                    "valid_from_event",
                    "valid_to_event",
                    "valid_at_event",
                    "temporal",
                )
            ):
                continue
            source_event = event_map.get(str(rel.get("source_id", "")))
            source_date = (
                self._coerce_date(source_event.lore_date)
                if source_event is not None
                else None
            )
            window = resolve_temporal_window(
                attrs,
                source_date,
                source_event_attributes=source_event.attributes
                if source_event
                else None,
                source_event_id=source_event.id if source_event else None,
                converter=self._date_parser.converter if self._date_parser else None,
                anchors=anchors,
            )
            if not window.is_valid:
                rel_id = str(rel.get("id", ""))
                conflicts.append(
                    TemporalConflict(
                        conflict_type="invalid_relation_window",
                        entity_id=rel_id,
                        entity_name=f"Relation {rel_id}",
                        problem_date=window.start,
                        message=window.error or "Invalid temporal relation window.",
                        suggestion="Fix the date range for this relation.",
                        severity=SeverityLevel.WARNING,
                        related_ids=[
                            str(rel.get("source_id", "")),
                            str(rel.get("target_id", "")),
                        ],
                        fingerprint=f"invalid-window:{rel_id}",
                    )
                )

        return conflicts

    def _analyze_character_lifespans(
        self,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
    ) -> tuple[list[CharacterLifespan], list[TemporalConflict]]:
        """Compute birth/death and lifespan violation data for every entity.

        Birth and death dates are resolved from relations whose ``rel_type``
        is ``"birth"`` or ``"death"`` (case-insensitive). The legacy date is
        taken from the relation's ``attributes["date"]`` value; if absent, it
        falls back to the ``lore_date`` of the event referenced by
        ``attributes["event_id"]``.

        Violating events are those that fall strictly before the birth date
        or strictly after the death date (only when the respective date is
        known).

        Args:
            entities: All entities in the world.
            events: All events in the world.
            relations: All relations as raw dicts.

        Returns:
            tuple: Lifespans and any malformed or out-of-lifespan conflicts.
        """
        event_map: dict[str, Event] = {e.id: e for e in events}
        entity_map: dict[str, Entity] = {entity.id: entity for entity in entities}

        lifespan_relations: dict[str, list[dict[str, Any]]] = defaultdict(list)
        related_event_ids: dict[str, set[str]] = defaultdict(set)
        conflicts: list[TemporalConflict] = []
        for rel in relations:
            source_id = str(rel.get("source_id", ""))
            target_id = str(rel.get("target_id", ""))
            endpoints = (source_id, target_id)
            for entity_id in endpoints:
                other_id = target_id if entity_id == source_id else source_id
                if entity_id in entity_map and other_id in event_map:
                    related_event_ids[entity_id].add(other_id)

            rel_type = str(rel.get("rel_type", "")).strip().casefold()
            if rel_type not in {"birth", "death", "revival"}:
                continue
            characters = [
                entity_map[endpoint]
                for endpoint in endpoints
                if endpoint in entity_map
                and entity_map[endpoint].type.casefold() == "character"
            ]
            rel_id = str(rel.get("id", ""))
            if not characters:
                conflicts.append(
                    TemporalConflict(
                        conflict_type="malformed_lifespan_relation",
                        entity_id=rel_id,
                        entity_name=f"Relation {rel_id}",
                        problem_date=None,
                        message=(
                            "Birth/death relation must have exactly one character "
                            "endpoint."
                        ),
                        suggestion="Connect the relation to one character.",
                        related_ids=list(endpoints),
                        fingerprint=f"malformed-lifespan:{rel_id}",
                    )
                )
                continue
            character = characters[0]
            if len(characters) > 1:
                target_entity = entity_map.get(target_id)
                if (
                    target_entity is not None
                    and target_entity.type.casefold() == "character"
                ):
                    character = target_entity
                conflicts.append(
                    TemporalConflict(
                        conflict_type="ambiguous_lifespan_relation",
                        entity_id=rel_id,
                        entity_name=f"Relation {rel_id}",
                        problem_date=None,
                        message=(
                            "Birth/death relation has two character endpoints; "
                            "the target is treated as the subject for compatibility."
                        ),
                        suggestion="Connect the relation to an event or add a date.",
                        related_ids=list(endpoints),
                        fingerprint=f"ambiguous-lifespan:{rel_id}",
                    )
                )
            lifespan_relations[character.id].append(rel)

        self._include_wikilink_events(events, entity_map, related_event_ids)

        from src.core.temporal_anchors import resolve_event_anchors

        converter = (
            self._date_parser.converter if self._date_parser is not None else None
        )
        anchors = resolve_event_anchors(events, converter)
        lifespans = []
        for entity in entities:
            rows = lifespan_relations.get(entity.id, [])
            if not rows:
                continue
            claims = character_claims(entity.id, rows, anchors, self._date_parser)
            lifespan, issues = self._summarize_lifespan(
                entity, claims, related_event_ids[entity.id], event_map, anchors
            )
            if lifespan is not None:
                lifespans.append(lifespan)
            conflicts.extend(issues)
        return lifespans, conflicts

    @staticmethod
    def _include_wikilink_events(
        events: list[Event],
        entities: dict[str, Entity],
        related: dict[str, set[str]],
    ) -> None:
        for event in events:
            texts = [event.description or ""]
            summary = event.attributes.get("_summary_data")
            if isinstance(summary, dict) and summary.get("text"):
                texts.append(str(summary["text"]))
            for text in texts:
                for link in WikiLinkParser.extract_links(text):
                    if link.is_id_based and link.target_id in entities:
                        related[str(link.target_id)].add(event.id)

    def _summarize_lifespan(
        self,
        entity: Entity,
        claims: list[LivingClaim],
        related_ids: set[str],
        events: dict[str, Event],
        anchors: dict[str, ResolvedTemporalBounds],
    ) -> tuple[CharacterLifespan | None, list[TemporalConflict]]:
        """Keep lifespan scalars and diagnostics tied to the same evidence."""
        if not claims:
            return None, []
        issues = self._lifespan_evidence_issues(entity, claims)
        violating = []
        evidence_ids = {claim.event_id for claim in claims}
        for event_id in sorted(related_ids - evidence_ids):
            bounds = anchors.get(f"event:{event_id}")
            if bounds is None or not definitely_outside_life(claims, bounds):
                continue
            event = events[event_id]
            violating.append(event_id)
            issues.append(
                TemporalConflict(
                    conflict_type="lifespan_violation",
                    entity_id=event_id,
                    entity_name=event.name,
                    problem_date=bounds.hard_start,
                    message=f"'{event.name}' falls outside {entity.name}'s recorded lifespan.",
                    suggestion="Review the Event timing and lifecycle associations.",
                    object_type="event",
                    related_ids=[entity.id, event_id],
                    fingerprint=f"lifespan:{entity.id}:{event_id}",
                )
            )
        birth = self._single_exact_boundary(claims, "birth")
        death = self._single_exact_boundary(claims, "death")
        if any(claim.kind == "revival" for claim in claims):
            birth = death = None
        duration = (
            (death - birth) / self._year_length
            if birth is not None and death is not None and birth < death
            else None
        )
        return CharacterLifespan(
            entity.id, entity.name, birth, death, duration, violating
        ), issues

    @staticmethod
    def _single_exact_boundary(claims: list[LivingClaim], kind: str) -> float | None:
        boundaries = [claim for claim in claims if claim.kind == kind]
        if len(boundaries) == 1 and boundaries[0].lower == boundaries[0].upper:
            return boundaries[0].lower
        return None

    @staticmethod
    def _lifespan_evidence_issues(
        entity: Entity, claims: list[LivingClaim]
    ) -> list[TemporalConflict]:
        issues = []
        for claim in claims:
            if claim.lower is not None and claim.upper is not None:
                continue
            issues.append(
                TemporalConflict(
                    conflict_type="unresolved_lifespan",
                    entity_id=entity.id,
                    entity_name=entity.name,
                    problem_date=None,
                    message=f"Timing for a {claim.kind} claim is unresolved.",
                    suggestion="Review the linked Event's authored timing.",
                    severity=SeverityLevel.INFO,
                    related_ids=[
                        claim.relation_id,
                        *([claim.event_id] if claim.event_id else []),
                    ],
                    fingerprint=f"unresolved-lifespan:{claim.relation_id}",
                )
            )
        for left, right, definite in competing_claims(claims):
            issues.append(
                TemporalConflict(
                    conflict_type="lifespan_boundary_conflict",
                    entity_id=entity.id,
                    entity_name=entity.name,
                    problem_date=left.lower if definite else None,
                    message=(
                        "Recorded lifecycle boundaries conflict."
                        if definite
                        else "Recorded lifecycle boundaries may conflict."
                    ),
                    suggestion="Review the timing and meaning of both claims.",
                    severity=SeverityLevel.WARNING if definite else SeverityLevel.INFO,
                    related_ids=[left.relation_id, right.relation_id],
                    fingerprint=f"lifespan-boundary:{left.relation_id}:{right.relation_id}",
                )
            )
        return issues

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _coerce_date(self, value: Any) -> float | None:
        """Coerce a lore-date value to float, parsing strings via DateParser.

        Numeric values are cast directly.  String values are parsed with
        :attr:`_date_parser` when available; unparseable strings are logged
        and skipped.

        Args:
            value: A numeric date or a string date expression (e.g.
                ``"1 MAY 1897"``).

        Returns:
            float | None: The date as a float timestamp, or ``None`` if
            the value cannot be converted.
        """
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and self._date_parser is not None:
            try:
                parsed = self._date_parser.parse_date(value)
                return self._date_parser.calculate_timestamp(parsed)
            except Exception:
                logger.warning(
                    "TemporalAnalyzer: could not parse date string %r", value
                )
        return None
