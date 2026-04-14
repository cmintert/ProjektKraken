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

    def __init__(self, db_service: "DatabaseService") -> None:
        """Initialise the analyzer with a database service.

        Args:
            db_service: A connected
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
        events: list[Event] = self.db_service.get_all_events()
        entities: list[Entity] = self.db_service.get_all_entities()
        relations: list[dict[str, Any]] = self.db_service.get_all_relations()

        cal = self.db_service.get_active_calendar_config()
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
        conflicts = self._detect_temporal_conflicts(relations)

        # Pre-build event date map once; reused by lifespan check to avoid
        # calling _coerce_date O(entities × events) times.
        event_dates: dict[str, float | None] = {
            e.id: self._coerce_date(e.lore_date) for e in events
        }
        lifespans = self._analyze_character_lifespans(entities, events, relations, event_dates)

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
        self, relations: list[dict[str, Any]]
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

        for rel in relations:
            attrs = rel.get("attributes", {})
            valid_from = attrs.get("valid_from")
            valid_to = attrs.get("valid_to")

            if valid_from is None or valid_to is None:
                continue

            from_float = self._coerce_date(valid_from)
            to_float = self._coerce_date(valid_to)
            if from_float is None or to_float is None:
                continue

            if from_float >= to_float:
                rel_id = rel.get("id", "")
                conflicts.append(
                    TemporalConflict(
                        conflict_type="invalid_relation_window",
                        entity_id=rel_id,
                        entity_name=f"Relation {rel_id}",
                        problem_date=from_float,
                        message=(
                            f"valid_from ({valid_from}) >= valid_to ({valid_to})"
                        ),
                        suggestion="Fix the date range for this relation.",
                        severity=SeverityLevel.WARNING,
                    )
                )

        return conflicts

    def _analyze_character_lifespans(
        self,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
        event_dates: dict[str, float | None] | None = None,
    ) -> list[CharacterLifespan]:
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
            list[CharacterLifespan]: One entry per entity that has at least
            one birth or death relation.
        """
        event_map: dict[str, Event] = {e.id: e for e in events}

        if event_dates is None:
            event_dates = {e.id: self._coerce_date(e.lore_date) for e in events}

        # Pre-bucket relations by target_id: O(R) instead of O(E*R).
        relations_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            target = rel.get("target_id")
            if target:
                relations_by_target[target].append(rel)

        lifespans: list[CharacterLifespan] = []

        for entity in entities:
            birth_date: float | None = None
            death_date: float | None = None
            has_lifespan_relation = False

            for rel in relations_by_target[entity.id]:
                rel_type = rel.get("rel_type", "").lower()
                attrs = rel.get("attributes", {})
                date = self._resolve_date(attrs, event_map)

                if "birth" in rel_type:
                    has_lifespan_relation = True
                    if date is not None and birth_date is None:
                        birth_date = date
                if "death" in rel_type:
                    has_lifespan_relation = True
                    if date is not None and death_date is None:
                        death_date = date

            if not has_lifespan_relation:
                continue

            violating: list[str] = []
            for event in events:
                event_date = event_dates.get(event.id)
                if event_date is None:
                    continue
                if birth_date is not None and event_date < birth_date:
                    violating.append(event.id)
                elif death_date is not None and event_date > death_date:
                    violating.append(event.id)

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

        return lifespans

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
        self, attrs: dict[str, Any], event_map: dict[str, Event]
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

        event_id = attrs.get("event_id")
        if event_id and event_id in event_map:
            return self._coerce_date(event_map[event_id].lore_date)

        return None
