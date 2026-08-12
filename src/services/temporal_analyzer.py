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
    EvidenceReference,
    SeverityLevel,
    TemporalAnalysisReport,
    TemporalConflict,
    TimelineGap,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_window import resolve_temporal_window
from src.services.text_parser import WikiLinkParser

if TYPE_CHECKING:
    from src.core.date_parser import DateParser
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

_GAP_THRESHOLD: float = 365.0 * 100.0  # 100 Gregorian years in days


class TemporalAnalyzer:
    """Analyzes temporal consistency and gaps in a world database.

    Runs three checks against the database via
    :class:`~src.services.db_service.DatabaseService`:

    - **Timeline gaps**: consecutive event pairs separated by more than
      :attr:`gap_threshold` lore-time units.
    - **Temporal conflicts**: relations whose ``valid_from``/``valid_to``
      attribute window is logically invalid (``valid_from >= valid_to``).
    - **Character lifespans**: per-entity birth/death tracking derived from
      relations whose ``rel_type`` contains ``"birth"`` or ``"death"``, plus
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

        # Pre-build event date map once; reused by lifespan check to avoid
        # calling _coerce_date O(entities × events) times.
        event_dates: dict[str, float | None] = {
            e.id: self._coerce_date(e.lore_date) for e in events
        }
        lifespans, lifespan_conflicts = self._analyze_character_lifespans(
            entities,
            events,
            relations,
            event_dates,
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

        if len(dated) < 2:
            return [], dated

        dated.sort(key=lambda x: x[0])
        gaps: list[TimelineGap] = []

        for (date_a, ev_a), (date_b, ev_b) in zip(dated, dated[1:]):
            duration = date_b - date_a
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

        event_map = {event.id: event for event in events or []}
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
                )
            ):
                continue
            source_event = event_map.get(str(rel.get("source_id", "")))
            source_date = (
                self._coerce_date(source_event.lore_date)
                if source_event is not None
                else None
            )
            window = resolve_temporal_window(attrs, source_date)
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

    def _analyze_character_lifespans(  # noqa: C901
        self,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
        event_dates: dict[str, float | None] | None = None,
    ) -> tuple[list[CharacterLifespan], list[TemporalConflict]]:
        """Compute birth/death and lifespan violation data for every entity.

        Birth and death dates are resolved from relations whose ``rel_type``
        contains ``"birth"`` or ``"death"`` (case-insensitive).  The date is
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
            event_dates: Optional pre-computed mapping of event_id → coerced
                lore date.  When provided the method skips per-event
                ``_coerce_date`` calls; when ``None`` it builds the map
                itself.

        Returns:
            tuple: Lifespans and any malformed or out-of-lifespan conflicts.
        """
        event_map: dict[str, Event] = {e.id: e for e in events}
        entity_map: dict[str, Entity] = {entity.id: entity for entity in entities}

        if event_dates is None:
            event_dates = {e.id: self._coerce_date(e.lore_date) for e in events}

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

            rel_type = str(rel.get("rel_type", "")).casefold()
            if "birth" not in rel_type and "death" not in rel_type:
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

        for event in events:
            texts = [event.description or ""]
            summary = event.attributes.get("_summary_data")
            if isinstance(summary, dict) and summary.get("text"):
                texts.append(str(summary["text"]))
            for text in texts:
                for link in WikiLinkParser.extract_links(text):
                    if link.is_id_based and link.target_id in entity_map:
                        related_event_ids[str(link.target_id)].add(event.id)

        lifespans: list[CharacterLifespan] = []

        for entity in entities:
            birth_date: float | None = None
            death_date: float | None = None
            has_lifespan_relation = False

            if entity.type.casefold() != "character":
                continue
            for rel in lifespan_relations[entity.id]:
                rel_type = rel.get("rel_type", "").lower()
                attrs = rel.get("attributes", {})
                source_id = str(rel.get("source_id", ""))
                target_id = str(rel.get("target_id", ""))
                event_endpoint = next(
                    (
                        endpoint
                        for endpoint in (source_id, target_id)
                        if endpoint in event_map
                    ),
                    None,
                )
                date = self._resolve_date(attrs, event_map, event_endpoint)
                if date is None:
                    rel_id = str(rel.get("id", ""))
                    conflicts.append(
                        TemporalConflict(
                            conflict_type="malformed_lifespan_relation",
                            entity_id=rel_id,
                            entity_name=f"Relation {rel_id}",
                            problem_date=None,
                            message=(
                                "Birth/death relation has no resolvable explicit "
                                "or event date."
                            ),
                            suggestion="Add a relation date or connect an event.",
                            related_ids=[source_id, target_id],
                            fingerprint=f"malformed-lifespan-date:{rel_id}",
                        )
                    )

                if "birth" in rel_type:
                    has_lifespan_relation = True
                    if date is not None and birth_date is None:
                        birth_date = date
                    elif (
                        date is not None
                        and birth_date is not None
                        and date != birth_date
                    ):
                        rel_id = str(rel.get("id", ""))
                        conflicts.append(
                            TemporalConflict(
                                conflict_type="ambiguous_lifespan_relation",
                                entity_id=rel_id,
                                entity_name=entity.name,
                                problem_date=date,
                                message="Character has conflicting birth dates.",
                                suggestion="Keep one authoritative birth relation.",
                                related_ids=[entity.id],
                                fingerprint=f"ambiguous-birth:{entity.id}:{rel_id}",
                            )
                        )
                if "death" in rel_type:
                    has_lifespan_relation = True
                    if date is not None and death_date is None:
                        death_date = date
                    elif (
                        date is not None
                        and death_date is not None
                        and date != death_date
                    ):
                        rel_id = str(rel.get("id", ""))
                        conflicts.append(
                            TemporalConflict(
                                conflict_type="ambiguous_lifespan_relation",
                                entity_id=rel_id,
                                entity_name=entity.name,
                                problem_date=date,
                                message="Character has conflicting death dates.",
                                suggestion="Keep one authoritative death relation.",
                                related_ids=[entity.id],
                                fingerprint=f"ambiguous-death:{entity.id}:{rel_id}",
                            )
                        )

            if not has_lifespan_relation:
                continue

            violating: list[str] = []
            for event_id in sorted(related_event_ids[entity.id]):
                event = event_map[event_id]
                event_date = event_dates.get(event.id)
                if event_date is None:
                    continue
                if birth_date is not None and event_date < birth_date:
                    violating.append(event.id)
                elif death_date is not None and event_date > death_date:
                    violating.append(event.id)

                if event.id in violating:
                    conflicts.append(
                        TemporalConflict(
                            conflict_type="lifespan_violation",
                            entity_id=event.id,
                            entity_name=event.name,
                            problem_date=event_date,
                            message=(
                                f"'{event.name}' falls outside {entity.name}'s "
                                "recorded lifespan."
                            ),
                            suggestion="Review the event date or lifespan relation.",
                            object_type="event",
                            related_ids=[entity.id, event.id],
                            evidence=[
                                EvidenceReference(
                                    evidence_id=f"event:{event.id}",
                                    object_type="event",
                                    object_id=event.id,
                                    object_name=event.name,
                                    field="lore_date",
                                    lore_date=event_date,
                                )
                            ],
                            fingerprint=(
                                f"lifespan:{entity.id}:{event.id}"
                            ),
                        )
                    )

            life_span_years: float | None = None
            if birth_date is not None and death_date is not None:
                life_span_years = (death_date - birth_date) / self._year_length

            lifespans.append(
                CharacterLifespan(
                    entity_id=entity.id,
                    entity_name=entity.name,
                    birth_date=birth_date,
                    death_date=death_date,
                    life_span_years=life_span_years,
                    violating_events=violating,
                )
            )

        return lifespans, conflicts

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

    def _resolve_date(
        self,
        attrs: dict[str, Any],
        event_map: dict[str, Event],
        event_endpoint: str | None = None,
    ) -> float | None:
        """Resolve a lore date from relation attributes.

        Checks ``attrs["date"]`` first; if absent, looks up
        ``attrs["event_id"]`` in *event_map* and returns that event's
        ``lore_date``.

        Args:
            attrs: Relation attributes dict.
            event_map: Mapping of event_id → Event for fast lookup.

        Returns:
            float | None: The resolved date, or None if not determinable.
        """
        if "date" in attrs and attrs["date"] is not None:
            return self._coerce_date(attrs["date"])

        if event_endpoint is not None and event_endpoint in event_map:
            return self._coerce_date(event_map[event_endpoint].lore_date)

        event_id = attrs.get("event_id")
        if event_id and event_id in event_map:
            return self._coerce_date(event_map[event_id].lore_date)

        return None
