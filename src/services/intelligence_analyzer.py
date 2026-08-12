"""Intelligence Analyzer Service.

AI-powered world analysis using RAG + LLM.  Detects plot holes in entity
narratives, infers missing relations between entities that share context,
and generates lore suggestions to fill timeline gaps.

All LLM calls are isolated per sub-analyzer so a single provider failure
does not prevent the others from running.  Each interaction is recorded in
the ``audit_log`` of the returned :class:`~src.core.analysis.IntelligenceReport`.

The three sub-analyses (plot_holes, relations, lore) are independent and run
concurrently via :class:`~concurrent.futures.ThreadPoolExecutor`. The analyzer
operates on a serialized click-time snapshot and never accesses a database
connection while model calls are running.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import TYPE_CHECKING, Any, Callable

from src.core.analysis import (
    AnalysisCoverage,
    AnalysisPreset,
    AnalysisScope,
    AnalysisScopeKind,
    AnalysisSectionStatus,
    EvidenceReference,
    EvidenceStrength,
    IntelligenceReport,
    LoreGapFiller,
    ParsedLoreSuggestion,
    PlotHole,
    RelationProposal,
    SeverityLevel,
)
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.services.temporal_analyzer import TemporalAnalyzer
from src.services.text_parser import WikiLinkParser

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService
    from src.services.llm_provider import Provider

logger = logging.getLogger(__name__)

CancellationCheck = Callable[[], bool]


class IntelligenceAnalysisCancelled(Exception):
    """Raised when an intelligence analysis job is cooperatively cancelled."""


class InvalidStructuredResponse(ValueError):
    """Raised after both the initial and repair JSON responses are invalid."""

    def __init__(self, message: str, requests: int = 2) -> None:
        super().__init__(message)
        self.requests = requests


def build_intelligence_analysis_snapshot(
    db_service: DatabaseService,
    *,
    world_id: str = "",
    analysis_type: str = "all",
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture a deep, serializable world snapshot on the database thread.

    Args:
        db_service: Worker-thread-owned database service.
        world_id: ID of the world being captured.
        analysis_type: Requested analysis scope.

    Returns:
        dict[str, Any]: Database-independent snapshot for the AI worker.
    """
    entities = [entity.to_dict() for entity in db_service.get_all_entities()]
    events = [event.to_dict() for event in db_service.get_all_events()]
    relations = db_service.get_all_relations()
    calendar_config = db_service.get_active_calendar_config()
    run_options = copy.deepcopy(options or {})
    snapshot = {
        "world_id": world_id,
        "analysis_type": analysis_type,
        "analysis_types": run_options.get("analysis_types", []),
        "scope": run_options.get("scope", AnalysisScope().to_dict()),
        "preset": run_options.get("preset", AnalysisPreset.BALANCED.value),
        "captured_at": time.time(),
        "entities": entities,
        "events": events,
        "relations": relations,
        "calendar_config": (
            calendar_config.to_dict() if calendar_config is not None else None
        ),
    }
    return copy.deepcopy(snapshot)


def _lore_date_to_year(value: float, converter: CalendarConverter | None) -> int:
    """Convert an absolute lore-date day count to a calendar year integer.

    Args:
        value: Absolute day count from the calendar epoch.
        converter: Optional :class:`~src.core.calendar.CalendarConverter` for
            accurate conversion.  Falls back to a 365-day Gregorian approximation
            when ``None``.

    Returns:
        int: The calendar year corresponding to *value*.
    """
    if converter is not None:
        try:
            return converter.from_float(value).year
        except Exception:
            pass
    return int(value // 365.0) + 1


# Maximum number of entities to analyse for plot holes (sorted by relation count).
_MAX_ENTITIES_FOR_PLOT_HOLES: int = 10

# Maximum number of candidate entity pairs to send to the LLM for relation inference.
_MAX_RELATION_CANDIDATES: int = 20

# Maximum number of timeline gaps to generate lore suggestions for.
_MAX_GAPS_FOR_LORE: int = 5

# Lore generation response field delimiters.
_LORE_FIELD_EVENT = "EVENT:"
_LORE_FIELD_DATE = "DATE:"
_LORE_FIELD_DESCRIPTION = "DESCRIPTION:"


class IntelligenceAnalyzer:
    """AI-powered analysis of a serialized world snapshot using RAG + LLM.

    Analyses the world database for three categories of insight:

    - **Plot holes**: Narrative inconsistencies in the top-connected entities,
      detected by asking an LLM to review each entity's temporal and relational
      context.
    - **Relation proposals**: Missing relations between entities that share tags
      or other contextual signals, inferred by the LLM.
    - **Lore suggestions**: Generated bridging events for timeline gaps detected
      by :class:`~src.services.temporal_analyzer.TemporalAnalyzer`.

    Args:
        snapshot: A database-independent world snapshot. A ``DatabaseService``
            is accepted temporarily for compatibility and is converted to a
            snapshot immediately.
        provider: Optional pre-built :class:`~src.services.llm_provider.Provider`
            instance.  When ``None`` (default) the analyzer creates one from
            the application's QSettings on first use.  Pass an explicit provider
            in tests to avoid real LLM calls.
    """

    def __init__(
        self,
        snapshot: dict[str, Any] | DatabaseService | None,
        provider: Provider | None = None,
    ) -> None:
        """Initialize the analyzer.

        Args:
            snapshot: Serialized world snapshot. A connected ``DatabaseService``
                is converted eagerly for compatibility with legacy command code.
            provider: Optional injectable provider.  Pass a pre-built
                :class:`~src.services.llm_provider.Provider` in tests to avoid
                real LLM calls; leave ``None`` in production to auto-select from
                application settings.
        """
        if isinstance(snapshot, dict):
            self._snapshot = copy.deepcopy(snapshot)
        elif snapshot is None:
            self._snapshot = {
                "world_id": "",
                "analysis_type": "all",
                "analysis_types": [],
                "scope": AnalysisScope().to_dict(),
                "preset": AnalysisPreset.BALANCED.value,
                "captured_at": time.time(),
                "entities": [],
                "events": [],
                "relations": [],
                "calendar_config": None,
            }
        else:
            self._snapshot = build_intelligence_analysis_snapshot(snapshot)
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate_coverage(self) -> dict[str, Any]:
        """Estimate eligible candidates and initial requests without a provider call."""
        entities = [
            Entity.from_dict(data) for data in self._snapshot.get("entities", [])
        ]
        events = [Event.from_dict(data) for data in self._snapshot.get("events", [])]
        relations = copy.deepcopy(self._snapshot.get("relations", []))
        scope = AnalysisScope.from_dict(self._snapshot.get("scope"))
        entities, events, relations = self._apply_scope(
            scope, entities, events, relations
        )
        try:
            preset = AnalysisPreset(
                str(self._snapshot.get("preset", AnalysisPreset.BALANCED.value))
            )
        except ValueError:
            preset = AnalysisPreset.BALANCED
        selected = {
            str(value) for value in self._snapshot.get("analysis_types", [])
        } or {"plot_holes", "relations", "lore"}
        event_ids_by_entity = self._event_ids_by_entity(relations, events)
        linked_ids_by_entity = self._linked_ids_by_entity(entities)
        existing_pairs = {
            (str(rel.get("source_id", "")), str(rel.get("target_id", "")))
            for rel in relations
        }
        relation_candidates = [
            pair
            for pair in self._find_relation_candidates(
                entities, event_ids_by_entity, linked_ids_by_entity
            )
            if (pair[0].id, pair[1].id) not in existing_pairs
            and (pair[1].id, pair[0].id) not in existing_pairs
        ]
        calendar_data = self._snapshot.get("calendar_config")
        calendar_config = (
            CalendarConfig.from_dict(calendar_data) if calendar_data else None
        )
        gaps = TemporalAnalyzer().analyze_data(
            entities=entities,
            events=events,
            relations=relations,
            calendar_config=calendar_config,
        ).timeline_gaps
        eligible = {
            "plot_holes": len(entities),
            "relations": len(relation_candidates),
            "lore": len(gaps),
        }
        initial_requests = sum(
            min(eligible[name], preset.limits[name])
            for name in selected
            if name in eligible
        )
        return {
            "eligible": {name: eligible[name] for name in selected if name in eligible},
            "estimated_initial_requests": initial_requests,
            "repair_retry_possible": True,
        }

    def analyze(
        self,
        analysis_type: str | None = None,
        on_partial: Callable[[str, Any], None] | None = None,
        is_cancelled: CancellationCheck | None = None,
    ) -> IntelligenceReport:
        """Run AI analysis and return an :class:`~src.core.analysis.IntelligenceReport`.

        The three sub-analyses run concurrently in a
        :class:`~concurrent.futures.ThreadPoolExecutor`; each receives its own
        :class:`~src.services.llm_provider.Provider` instance so
        ``CircuitBreaker`` state is not shared across threads.

        Args:
            analysis_type: Optional override controlling which sub-analyses run.
                When omitted, uses the scope stored in the snapshot. One of
                ``"all"`` | ``"plot_holes"`` | ``"relations"`` | ``"lore"``.
            on_partial: Optional callback invoked on the calling thread as each
                sub-analysis completes, before the final report is returned.
                Called with ``(result_type, raw_result)`` where *result_type* is
                ``"holes"``, ``"relations"``, or ``"lore"`` and *raw_result* is
                the tuple returned by that sub-analyzer.  Not called for failed
                sub-analyses.
            is_cancelled: Thread-safe callback returning whether cancellation
                has been requested.

        Returns:
            IntelligenceReport: Populated report.  Sub-sections that were not
            requested are empty lists.
        """
        cancellation_check = is_cancelled or (lambda: False)
        self._raise_if_cancelled(cancellation_check)

        requested_type = analysis_type or str(
            self._snapshot.get("analysis_type", "all")
        )
        valid_types = {"all", "plot_holes", "relations", "lore"}
        if requested_type not in valid_types:
            requested_type = "all"

        all_entities = [
            Entity.from_dict(data) for data in self._snapshot.get("entities", [])
        ]
        all_events = [
            Event.from_dict(data) for data in self._snapshot.get("events", [])
        ]
        all_relations = copy.deepcopy(self._snapshot.get("relations", []))
        scope = AnalysisScope.from_dict(self._snapshot.get("scope"))
        entities, events, relations = self._apply_scope(
            scope,
            all_entities,
            all_events,
            all_relations,
        )
        try:
            preset = AnalysisPreset(
                str(self._snapshot.get("preset", AnalysisPreset.BALANCED.value))
            )
        except ValueError:
            preset = AnalysisPreset.BALANCED
        configured_types = {
            str(value) for value in self._snapshot.get("analysis_types", [])
        }
        requested_types = (
            configured_types
            if configured_types
            else (
                {"plot_holes", "relations", "lore"}
                if requested_type == "all"
                else {requested_type}
            )
        )
        calendar_data = self._snapshot.get("calendar_config")
        snapshot_calendar_config = (
            CalendarConfig.from_dict(calendar_data) if calendar_data is not None else None
        )

        temporal_report: Any | None = None
        if "lore" in requested_types:
            temporal_report = TemporalAnalyzer().analyze_data(
                entities=entities,
                events=events,
                relations=relations,
                calendar_config=snapshot_calendar_config,
            )

        # ------------------------------------------------------------------
        # Phase 2: build tasks.  Each task gets its own provider so that
        # CircuitBreaker mutable state is not shared across threads.
        # functools.partial binds the provider immediately — no closure-capture bug.
        # ------------------------------------------------------------------
        tasks: dict[str, Any] = {}

        if "plot_holes" in requested_types:
            tasks["holes"] = partial(
                self._detect_plot_holes,
                self._get_provider(),
                entities,
                relations,
                events,
                cancellation_check,
                preset.limits["plot_holes"],
            )

        if "relations" in requested_types:
            tasks["relations"] = partial(
                self._infer_relations,
                self._get_provider(),
                entities,
                relations,
                cancellation_check,
                preset.limits["relations"],
                events,
            )

        if "lore" in requested_types and temporal_report is not None:
            tasks["lore"] = partial(
                self._generate_lore,
                self._get_provider(),
                temporal_report,
                events,
                cancellation_check,
                preset.limits["lore"],
            )

        # Derive model name from first provider before threads start.
        model_name = "unknown"
        if tasks:
            # Peek at metadata via a temporary provider (cheap — no API call).
            model_name = self._get_provider().metadata().get("generation_model", "unknown")

        # ------------------------------------------------------------------
        # Phase 3: run sub-analyses concurrently.
        # ------------------------------------------------------------------
        results = self._execute_tasks(tasks, on_partial, cancellation_check)

        # ------------------------------------------------------------------
        # Phase 4: collect results.
        # ------------------------------------------------------------------
        plot_holes: list[PlotHole] = []
        relation_proposals: list[RelationProposal] = []
        lore_suggestions: list[LoreGapFiller] = []
        audit_log: list[dict[str, Any]] = []
        coverage: dict[str, AnalysisCoverage] = {}
        section_statuses: dict[str, AnalysisSectionStatus] = {}
        token_usage: dict[str, int] = defaultdict(int)
        report_calendar_config: Any | None = None

        if results.get("holes") is not None:
            holes, holes_audit, holes_coverage = results["holes"]
            plot_holes.extend(holes)
            audit_log.extend(holes_audit)
            coverage["plot_holes"] = holes_coverage

        if results.get("relations") is not None:
            proposals, rel_audit, rel_coverage = results["relations"]
            relation_proposals.extend(proposals)
            audit_log.extend(rel_audit)
            coverage["relations"] = rel_coverage

        if results.get("lore") is not None:
            suggestions, lore_audit, report_calendar_config, lore_coverage = results[
                "lore"
            ]
            lore_suggestions.extend(suggestions)
            audit_log.extend(lore_audit)
            coverage["lore"] = lore_coverage

        section_statuses = self._derive_section_statuses(requested_types, coverage)
        token_usage = self._sum_token_usage(audit_log)

        return IntelligenceReport(
            timestamp=time.time(),
            plot_holes=plot_holes,
            relation_proposals=relation_proposals,
            lore_suggestions=lore_suggestions,
            analysis_model=model_name,
            audit_log=audit_log,
            calendar_config=report_calendar_config,
            snapshot_timestamp=float(
                self._snapshot.get("captured_at", time.time())
            ),
            world_id=str(self._snapshot.get("world_id", "")),
            scope=scope,
            preset=preset,
            section_statuses=section_statuses,
            coverage=coverage,
            provider_metadata=(
                self._get_provider().metadata() if tasks else {}
            ),
            token_usage=token_usage,
        )

    # ------------------------------------------------------------------
    # Sub-analyzers
    # ------------------------------------------------------------------

    def _detect_plot_holes(
        self,
        provider: Provider,
        entities: list[Any],
        relations: list[dict[str, Any]],
        events: list[Any],
        is_cancelled: CancellationCheck,
        limit: int = _MAX_ENTITIES_FOR_PLOT_HOLES,
    ) -> tuple[list[PlotHole], list[dict[str, Any]], AnalysisCoverage]:
        """Detect plot holes in entity narratives via LLM analysis.

        Selects the top :data:`_MAX_ENTITIES_FOR_PLOT_HOLES` entities by
        total relation count, builds a context prompt for each, and asks
        the LLM to identify inconsistencies.

        Does not access the database — all data is pre-fetched by the caller
        so this method is safe to run in a worker thread.

        Args:
            provider: The LLM provider to use.
            entities: All entities in the world (pre-fetched by caller).
            relations: All relations in the world (pre-fetched by caller).
            events: All events in the world (pre-fetched by caller).
            is_cancelled: Thread-safe cancellation check.

        Returns:
            tuple: ``(plot_holes, audit_log)`` where *plot_holes* is a list
            of :class:`~src.core.analysis.PlotHole` objects and *audit_log*
            contains one dict per LLM call (or error).
        """
        audit_log: list[dict[str, Any]] = []
        plot_holes: list[PlotHole] = []

        if not entities:
            return plot_holes, audit_log, AnalysisCoverage()

        # Count relations per entity (source or target)
        relation_count: dict[str, int] = defaultdict(int)
        for rel in relations:
            relation_count[rel.get("source_id", "")] += 1
            relation_count[rel.get("target_id", "")] += 1

        dated_event_ids = {
            event.id
            for event in events
            if isinstance(event.lore_date, (int, float))
        }
        ranked_entities = sorted(
            entities,
            key=lambda entity: (
                -sum(
                    1
                    for rel in relations
                    if entity.id in {
                        rel.get("source_id", ""),
                        rel.get("target_id", ""),
                    }
                    and (
                        rel.get("source_id", "") in dated_event_ids
                        or rel.get("target_id", "") in dated_event_ids
                    )
                ),
                -relation_count[entity.id],
                -int(bool((entity.description or "").strip())),
                entity.id,
            ),
        )
        top_entities = ranked_entities[:limit]
        coverage = AnalysisCoverage(eligible=len(ranked_entities))

        event_map = {e.id: e for e in events}
        entity_name_map: dict[str, str] = {e.id: e.name for e in entities}
        relations_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            relations_by_entity[rel.get("source_id", "")].append(rel)
            relations_by_entity[rel.get("target_id", "")].append(rel)

        for entity in top_entities:
            self._raise_if_cancelled(is_cancelled)
            evidence = self._build_plot_hole_evidence(
                entity,
                relations_by_entity[entity.id],
                event_map,
                entity_name_map,
            )
            prompt = self._build_plot_hole_prompt(
                entity,
                relations_by_entity[entity.id],
                event_map,
                entity_name_map,
                evidence,
            )
            coverage.attempted += 1
            try:
                payload, result, request_count = self._generate_json(
                    provider,
                    prompt,
                    is_cancelled,
                    lambda value: self._parse_plot_hole_json(
                        value, entity, evidence
                    ),
                )
                coverage.requests += request_count
                self._raise_if_cancelled(is_cancelled)
                response_text = result.get("text", "")
                audit_log.append(
                    self._make_audit_entry(
                        "plot_hole_detection",
                        model=result.get("model", "unknown"),
                        entity_id=entity.id,
                        prompt_length=len(prompt),
                        response_length=len(response_text),
                        usage=result.get("usage", {}),
                    )
                )
                parsed = self._parse_plot_hole_json(payload, entity, evidence)
                if parsed is not None:
                    plot_holes.append(parsed)
                coverage.succeeded += 1
            except IntelligenceAnalysisCancelled:
                raise
            except Exception as exc:
                coverage.requests += int(getattr(exc, "requests", 0))
                logger.error(
                    "plot hole detection failed for entity %s: %s", entity.id, exc
                )
                audit_log.append(
                    self._make_audit_entry(
                        "plot_hole_detection",
                        error=str(exc),
                        entity_id=entity.id,
                    )
                )
                coverage.failed += 1
                coverage.errors.append(str(exc))

        return plot_holes, audit_log, coverage

    def _infer_relations(
        self,
        provider: Provider,
        entities: list[Any],
        relations: list[dict[str, Any]],
        is_cancelled: CancellationCheck,
        limit: int = _MAX_RELATION_CANDIDATES,
        events: list[Any] | None = None,
    ) -> tuple[list[RelationProposal], list[dict[str, Any]], AnalysisCoverage]:
        """Infer missing relations between entity pairs that share context.

        Candidate pairs are entities sharing at least one tag.  Pairs that
        already have an existing relation in either direction are skipped.
        At most :data:`_MAX_RELATION_CANDIDATES` pairs are evaluated.

        Args:
            provider: The LLM provider to use.
            entities: All entities in the world (pre-fetched by caller).
            relations: All relations in the world (pre-fetched by caller).
            is_cancelled: Thread-safe cancellation check.

        Returns:
            tuple: ``(proposals, audit_log)``.
        """
        audit_log: list[dict[str, Any]] = []
        proposals: list[RelationProposal] = []

        if not entities:
            return proposals, audit_log, AnalysisCoverage()

        existing_pairs: set[tuple[str, str]] = {
            (rel.get("source_id", ""), rel.get("target_id", ""))
            for rel in relations
        }

        event_ids_by_entity = self._event_ids_by_entity(relations, events or [])
        linked_ids_by_entity = self._linked_ids_by_entity(entities)
        candidates = sorted(
            self._find_relation_candidates(
                entities,
                event_ids_by_entity,
                linked_ids_by_entity,
            ),
            key=lambda pair: (
                -len(
                    set(pair[0].attributes.get("_tags", []))
                    & set(pair[1].attributes.get("_tags", []))
                ),
                -len(
                    event_ids_by_entity.get(pair[0].id, set())
                    & event_ids_by_entity.get(pair[1].id, set())
                ),
                -int(
                    pair[1].id in linked_ids_by_entity.get(pair[0].id, set())
                    or pair[0].id in linked_ids_by_entity.get(pair[1].id, set())
                ),
                pair[0].id,
                pair[1].id,
            ),
        )
        eligible_candidates = [
            pair
            for pair in candidates
            if (pair[0].id, pair[1].id) not in existing_pairs
            and (pair[1].id, pair[0].id) not in existing_pairs
        ]
        coverage = AnalysisCoverage(eligible=len(eligible_candidates))

        for source, target in eligible_candidates[:limit]:
            self._raise_if_cancelled(is_cancelled)
            evidence = self._build_relation_evidence(
                source,
                target,
                event_ids_by_entity,
                linked_ids_by_entity,
                events or [],
            )
            prompt = self._build_relation_inference_prompt(source, target, evidence)
            coverage.attempted += 1
            try:
                payload, result, request_count = self._generate_json(
                    provider,
                    prompt,
                    is_cancelled,
                    lambda value: self._parse_relation_json(
                        value, source, target, evidence
                    ),
                )
                coverage.requests += request_count
                self._raise_if_cancelled(is_cancelled)
                audit_log.append(
                    self._make_audit_entry(
                        "relation_inference",
                        model=result.get("model", "unknown"),
                        source_id=source.id,
                        target_id=target.id,
                        usage=result.get("usage", {}),
                    )
                )
                proposal = self._parse_relation_json(
                    payload,
                    source,
                    target,
                    evidence,
                )
                if proposal is not None:
                    proposals.append(proposal)
                coverage.succeeded += 1
            except IntelligenceAnalysisCancelled:
                raise
            except Exception as exc:
                coverage.requests += int(getattr(exc, "requests", 0))
                logger.error(
                    "relation inference failed for %s/%s: %s",
                    source.id,
                    target.id,
                    exc,
                )
                audit_log.append(
                    self._make_audit_entry(
                        "relation_inference",
                        error=str(exc),
                        source_id=source.id,
                        target_id=target.id,
                    )
                )
                coverage.failed += 1
                coverage.errors.append(str(exc))

        return proposals, audit_log, coverage

    def _generate_lore(
        self,
        provider: Provider,
        temporal_report: Any,
        events: list[Any],
        is_cancelled: CancellationCheck,
        limit: int = _MAX_GAPS_FOR_LORE,
    ) -> tuple[
        list[LoreGapFiller],
        list[dict[str, Any]],
        Any | None,
        AnalysisCoverage,
    ]:
        """Generate bridging lore suggestions for timeline gaps.

        Uses a pre-computed :class:`~src.services.temporal_analyzer.TemporalAnalysisReport`
        and pre-fetched events so this method performs no database access and
        is safe to run in a worker thread.

        Args:
            provider: The LLM provider to use.
            temporal_report: Pre-computed temporal analysis report from the
                calling thread (contains timeline gaps and calendar config).
            events: All events in the world (pre-fetched by caller).
            is_cancelled: Thread-safe cancellation check.

        Returns:
            tuple: ``(suggestions, audit_log, calendar_config)`` where
            *calendar_config* is forwarded from the temporal report so the
            caller can attach it to the returned
            :class:`~src.core.analysis.IntelligenceReport`.
        """
        audit_log: list[dict[str, Any]] = []
        suggestions: list[LoreGapFiller] = []

        calendar_config = temporal_report.calendar_config
        all_gaps = sorted(
            temporal_report.timeline_gaps,
            key=lambda gap: (-gap.gap_duration, gap.start_date),
        )
        gaps = all_gaps[:limit]
        coverage = AnalysisCoverage(eligible=len(all_gaps))
        if not gaps:
            return suggestions, audit_log, calendar_config, coverage

        converter: CalendarConverter | None = None
        if calendar_config is not None:
            try:
                converter = CalendarConverter(calendar_config)
            except Exception:
                logger.debug("_generate_lore: failed to build CalendarConverter")

        # Only include events with numeric lore dates to avoid TypeError when
        # comparing float with str in Python 3.
        sorted_events = sorted(
            [e for e in events if isinstance(e.lore_date, (int, float))],
            key=lambda e: float(e.lore_date),
        )

        for gap in gaps:
            self._raise_if_cancelled(is_cancelled)
            events_before = [e for e in sorted_events if e.lore_date <= gap.start_date]
            events_after = [e for e in sorted_events if e.lore_date >= gap.end_date]

            if not events_before or not events_after:
                continue

            prompt = self._build_lore_generation_prompt(
                gap, events_before[-1], events_after[0], converter
            )
            evidence = [
                self._event_evidence(events_before[-1]),
                self._event_evidence(events_after[0]),
            ]
            coverage.attempted += 1
            try:
                payload, result, request_count = self._generate_json(
                    provider,
                    prompt,
                    is_cancelled,
                    lambda value: self._parse_lore_json(value, gap, evidence),
                )
                coverage.requests += request_count
                self._raise_if_cancelled(is_cancelled)
                audit_log.append(
                    self._make_audit_entry(
                        "lore_generation",
                        model=result.get("model", "unknown"),
                        gap_start=gap.start_date,
                        gap_end=gap.end_date,
                        usage=result.get("usage", {}),
                    )
                )
                filler = self._parse_lore_json(payload, gap, evidence)
                if filler is not None:
                    suggestions.append(filler)
                coverage.succeeded += 1
            except IntelligenceAnalysisCancelled:
                raise
            except Exception as exc:
                coverage.requests += int(getattr(exc, "requests", 0))
                logger.error(
                    "lore generation failed for gap %.0f-%.0f: %s",
                    gap.start_date,
                    gap.end_date,
                    exc,
                )
                audit_log.append(
                    self._make_audit_entry(
                        "lore_generation",
                        error=str(exc),
                        gap_start=gap.start_date,
                        gap_end=gap.end_date,
                    )
                )
                coverage.failed += 1
                coverage.errors.append(str(exc))

        return suggestions, audit_log, calendar_config, coverage

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_plot_hole_prompt(
        self,
        entity: Any,
        entity_relations: list[dict[str, Any]],
        event_map: dict[str, Any],
        entity_name_map: dict[str, str],
        evidence: list[EvidenceReference] | None = None,
    ) -> str:
        """Build a plot-hole detection prompt for a single entity.

        Args:
            entity: The entity to analyse.
            entity_relations: All relations involving this entity.
            event_map: Mapping of event_id → Event for date resolution.
            entity_name_map: Mapping of entity_id → entity name for resolving
                relation targets to human-readable names.

        Returns:
            str: Formatted prompt string.
        """

        def _other_name(rel: dict[str, Any]) -> str:
            other_id = (
                rel.get("source_id", "")
                if rel.get("target_id", "") == entity.id
                else rel.get("target_id", "")
            )
            if other_id in entity_name_map:
                return entity_name_map[other_id]
            ev = event_map.get(other_id)
            if ev:
                return ev.name
            return other_id

        def _rel_line(rel: dict[str, Any]) -> str:
            rel_type = rel.get("rel_type", "unknown")
            other = _other_name(rel)
            if rel.get("target_id", "") == entity.id:
                return f"- {other} --{rel_type}--> {entity.name}"
            else:
                return f"- {entity.name} --{rel_type}--> {other}"

        rel_lines = "\n".join(_rel_line(rel) for rel in entity_relations[:20])
        evidence_json = json.dumps(
            [item.to_dict() for item in evidence or []],
            ensure_ascii=False,
        )
        return (
            f"Analyse this character/location for logical inconsistencies or plot holes:\n\n"
            f"Name: {entity.name}\n"
            f"Type: {getattr(entity, 'type', 'Unknown')}\n"
            f"Description: {entity.description or 'None'}\n\n"
            f"Relations use directed notation: A --relation--> B means A [relation] B.\n"
            f"Relations:\n{rel_lines or '(none)'}\n\n"
            f"Evidence records (cite only their evidence_id values):\n"
            f"{evidence_json}\n\n"
            "Return exactly one JSON object with keys: has_issue (boolean), "
            "issue_kind (temporal_contradiction, logical_conflict, "
            "missing_context, or characterization_conflict), description, "
            "severity (high, medium, or low), suggested_resolution, "
            "confidence (0-1), and evidence_ids (array). Do not use markdown."
        )

    def _build_relation_inference_prompt(
        self,
        source: Any,
        target: Any,
        evidence: list[EvidenceReference] | None = None,
    ) -> str:
        """Build a relation inference prompt for an entity pair.

        Args:
            source: Source entity.
            target: Target entity.

        Returns:
            str: Formatted prompt string.
        """
        evidence_json = json.dumps(
            [item.to_dict() for item in evidence or []],
            ensure_ascii=False,
        )
        return (
            f"Should these two entities have a direct relation?\n\n"
            f"{source.name} ({getattr(source, 'type', 'unknown')})\n"
            f"SOURCE: {source.id}\n"
            f"Description: {source.description or 'None'}\n"
            f"Tags: {source.attributes.get('_tags', [])}\n\n"
            f"{target.name} ({getattr(target, 'type', 'unknown')})\n"
            f"TARGET: {target.id}\n"
            f"Description: {target.description or 'None'}\n"
            f"Tags: {target.attributes.get('_tags', [])}\n\n"
            f"Relations use directed notation: SOURCE --RELATION_TYPE--> TARGET means "
            f"SOURCE [RELATION_TYPE] TARGET. Use active-voice relation types "
            f"(e.g. 'employs' not 'employed_by', 'governs' not 'governed_by').\n\n"
            f"Evidence records:\n{evidence_json}\n\n"
            "Return exactly one JSON object with keys: should_relate (boolean), "
            "source_id, target_id, relation_type, confidence (0-1), reasoning, "
            "and evidence_ids (array). Cite only supplied evidence IDs and do not "
            "use markdown."
        )

    def _build_lore_generation_prompt(
        self,
        gap: Any,
        before_event: Any,
        after_event: Any,
        converter: CalendarConverter | None = None,
    ) -> str:
        """Build a lore generation prompt for a timeline gap.

        Args:
            gap: The :class:`~src.core.analysis.TimelineGap` to fill.
            before_event: The last event before the gap.
            after_event: The first event after the gap.
            converter: Optional :class:`~src.core.calendar.CalendarConverter`
                used to format lore dates as human-readable years.  Falls back
                to a 365-day Gregorian approximation when ``None``.

        Returns:
            str: Formatted prompt string.
        """
        gap_years = int(gap.gap_duration / 365)
        before_year = _lore_date_to_year(before_event.lore_date, converter)
        after_year = _lore_date_to_year(after_event.lore_date, converter)
        before_evidence = self._event_evidence(before_event)
        after_evidence = self._event_evidence(after_event)
        return (
            f"There is a {gap_years}-year gap in the timeline.\n\n"
            f"Last event: Year {before_year} — {before_event.name}\n"
            f"Description: {before_event.description or 'None'}\n\n"
            f"Next event: Year {after_year} — {after_event.name}\n"
            f"Description: {after_event.description or 'None'}\n\n"
            "This is a creative suggestion, not a factual finding. Generate 2-3 "
            "plausible bridging events. Return exactly one JSON object with keys "
            '"suggestions" (an array of objects with name, date, and description) '
            'and "evidence_ids" (an array containing both boundary evidence IDs). '
            f"Boundary evidence: {json.dumps([before_evidence.to_dict(), after_evidence.to_dict()], ensure_ascii=False)}. "
            "Do not use markdown."
        )

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    def _parse_plot_holes(
        self, response: str, entity: Any
    ) -> list[PlotHole]:
        """Parse an LLM response into a list of PlotHoles.

        Splits on ``PLOT HOLE:`` markers and extracts description, severity,
        and optional resolution from each block.

        Args:
            response: Raw LLM response text.
            entity: The entity the plot holes concern.

        Returns:
            list[PlotHole]: Parsed plot holes (may be empty).
        """
        holes: list[PlotHole] = []
        parts = response.split("PLOT HOLE:")
        for idx, part in enumerate(parts[1:]):
            lines = part.strip().split("\n")
            description = lines[0].strip() if lines else ""
            if not description:
                continue

            severity = SeverityLevel.WARNING
            part_lower = part.lower()
            if "severity: high" in part_lower:
                severity = SeverityLevel.CRITICAL
            elif "severity: low" in part_lower:
                severity = SeverityLevel.INFO

            resolution: str | None = None
            if "RESOLUTION:" in part:
                resolution = part.split("RESOLUTION:")[1].split("\n")[0].strip() or None

            confidence = self._extract_confidence_from_block(part, default=0.75)

            holes.append(
                PlotHole(
                    issue_id=f"hole_{entity.id}_{idx}",
                    entity_id=entity.id,
                    entity_name=entity.name,
                    description=description,
                    severity=severity,
                    suggested_resolution=resolution,
                    confidence=confidence,
                )
            )
        return holes

    def _extract_confidence_from_block(self, text: str, default: float) -> float:
        """Extract and clamp a CONFIDENCE value from an LLM response block.

        Args:
            text: Response block for a single parsed item.
            default: Fallback confidence when no parseable value exists.

        Returns:
            float: Confidence clamped to [0.0, 1.0].
        """
        if "CONFIDENCE:" not in text:
            return default

        try:
            raw = text.split("CONFIDENCE:")[1].split("\n")[0].strip()
            parsed = float(raw)
            return max(0.0, min(1.0, parsed))
        except (ValueError, IndexError):
            return default

    def _parse_relation_proposal(
        self, response: str, source: Any, target: Any
    ) -> RelationProposal | None:
        """Parse an LLM relation-inference response.

        Returns ``None`` when the response does not indicate a relation should
        exist.

        Args:
            response: Raw LLM response text.
            source: Source entity.
            target: Target entity.

        Returns:
            RelationProposal | None: Parsed proposal or ``None``.
        """
        if "yes" not in response.lower():
            return None

        relation_type = "related"
        if "RELATION_TYPE:" in response:
            relation_type = (
                response.split("RELATION_TYPE:")[1].split("\n")[0].strip()
                or "related"
            )

        confidence = self._extract_confidence_from_block(response, default=0.7)

        reasoning = ""
        if "REASONING:" in response:
            reasoning = response.split("REASONING:")[1].strip()

        # Honour the SOURCE:/TARGET: fields the LLM may emit. If it chose the
        # opposite direction from the candidate pair, swap so the proposal
        # reflects the LLM's intent.
        actual_source, actual_target = source, target
        if "SOURCE:" in response and "TARGET:" in response:
            llm_source = response.split("SOURCE:")[1].split("\n")[0].strip().lower()
            llm_target = response.split("TARGET:")[1].split("\n")[0].strip().lower()
            src_name_lower = source.name.lower()
            tgt_name_lower = target.name.lower()
            if llm_source == tgt_name_lower and llm_target == src_name_lower:
                actual_source, actual_target = target, source

        return RelationProposal(
            source_id=actual_source.id,
            source_name=actual_source.name,
            target_id=actual_target.id,
            target_name=actual_target.name,
            suggested_relation_type=relation_type,
            reasoning=reasoning,
            confidence=confidence,
        )

    def _parse_lore_suggestions(
        self, response: str, gap: Any
    ) -> LoreGapFiller | None:
        """Parse an LLM lore-generation response into a LoreGapFiller.

        Splits on ``EVENT:`` markers and extracts name, date, and description fields.
        Returns ``None`` when no parseable event blocks are found.

        Args:
            response: Raw LLM response text.
            gap: The :class:`~src.core.analysis.TimelineGap` being filled.

        Returns:
            LoreGapFiller | None: Parsed filler or ``None``.
        """
        suggestions: list[ParsedLoreSuggestion] = []
        parts = response.split(_LORE_FIELD_EVENT)
        for part in parts[1:]:
            text = part.strip()
            if not text:
                continue
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            name = lines[0] if lines else ""
            date_str = ""
            description = ""
            for line in lines[1:]:
                if line.startswith(_LORE_FIELD_DATE):
                    date_str = line.replace(_LORE_FIELD_DATE, "", 1).strip()
                elif line.startswith(_LORE_FIELD_DESCRIPTION):
                    description = line.replace(_LORE_FIELD_DESCRIPTION, "", 1).strip()
            suggestions.append(ParsedLoreSuggestion(
                name=name,
                date_str=date_str,
                description=description,
            ))

        if not suggestions:
            return None

        return LoreGapFiller(
            gap_id=f"gap_{gap.start_date:.0f}_{gap.end_date:.0f}",
            start_date=gap.start_date,
            end_date=gap.end_date,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_section_statuses(
        requested_types: set[str], coverage: dict[str, AnalysisCoverage]
    ) -> dict[str, AnalysisSectionStatus]:
        statuses: dict[str, AnalysisSectionStatus] = {}
        for name in ("plot_holes", "relations", "lore"):
            if name not in requested_types:
                statuses[name] = AnalysisSectionStatus.SKIPPED
                continue
            section_coverage = coverage.setdefault(name, AnalysisCoverage())
            statuses[name] = section_coverage.status
        return statuses

    @staticmethod
    def _sum_token_usage(audit_log: list[dict[str, Any]]) -> dict[str, int]:
        token_usage: dict[str, int] = defaultdict(int)
        for entry in audit_log:
            usage = entry.get("usage", {})
            if not isinstance(usage, dict):
                continue
            for key, value in usage.items():
                if isinstance(value, int):
                    token_usage[key] += value
        return dict(token_usage)

    def _apply_scope(
        self,
        scope: AnalysisScope,
        entities: list[Entity],
        events: list[Event],
        relations: list[dict[str, Any]],
    ) -> tuple[list[Entity], list[Event], list[dict[str, Any]]]:
        """Return the deterministic object subgraph selected by ``scope``."""
        objects: dict[str, Any] = {entity.id: entity for entity in entities}
        objects.update({event.id: event for event in events})
        if scope.kind == AnalysisScopeKind.WHOLE_WORLD:
            selected_ids = set(objects)
        elif scope.kind in {
            AnalysisScopeKind.CURRENT_ITEM,
            AnalysisScopeKind.SELECTION,
        }:
            seed_ids = {item_id for item_id in scope.item_ids if item_id in objects}
            selected_ids = set(seed_ids)
            for relation in relations:
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if source_id in seed_ids or target_id in seed_ids:
                    selected_ids.update((source_id, target_id))
        elif scope.kind == AnalysisScopeKind.TAGS:
            wanted_tags = set(scope.tags)
            selected_ids = {
                item.id
                for item in objects.values()
                if wanted_tags & set(item.attributes.get("_tags", []))
            }
        else:
            start = float("-inf") if scope.start_date is None else scope.start_date
            end = float("inf") if scope.end_date is None else scope.end_date
            seed_ids = {
                event.id
                for event in events
                if isinstance(event.lore_date, (int, float))
                and start <= float(event.lore_date) <= end
            }
            selected_ids = set(seed_ids)
            entity_ids = {entity.id for entity in entities}
            for relation in relations:
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if source_id in seed_ids and target_id in entity_ids:
                    selected_ids.add(target_id)
                elif target_id in seed_ids and source_id in entity_ids:
                    selected_ids.add(source_id)

        scoped_relations = [
            relation
            for relation in relations
            if str(relation.get("source_id", "")) in selected_ids
            and str(relation.get("target_id", "")) in selected_ids
        ]
        return (
            [entity for entity in entities if entity.id in selected_ids],
            [event for event in events if event.id in selected_ids],
            scoped_relations,
        )

    def _generate_json(
        self,
        provider: Provider,
        prompt: str,
        is_cancelled: CancellationCheck,
        validator: Callable[[dict[str, Any]], Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        """Generate and parse strict JSON, with exactly one disclosed repair retry."""
        self._raise_if_cancelled(is_cancelled)
        try:
            first = provider.generate(prompt, temperature=0.2)
        except Exception as exc:
            error = InvalidStructuredResponse(str(exc), requests=1)
            raise error from exc
        self._raise_if_cancelled(is_cancelled)
        try:
            payload = self._decode_json_object(str(first.get("text", "")))
            if validator is not None:
                validator(payload)
            return payload, first, 1
        except (TypeError, ValueError) as first_error:
            repair_prompt = (
                f"{prompt}\n\nThe previous response was invalid: {first_error}. "
                "Return only one corrected JSON object matching the requested "
                f"schema. Previous response:\n{first.get('text', '')}"
            )
            try:
                repaired = provider.generate(repair_prompt, temperature=0.0)
            except Exception as exc:
                raise InvalidStructuredResponse(str(exc)) from exc
            self._raise_if_cancelled(is_cancelled)
            try:
                payload = self._decode_json_object(str(repaired.get("text", "")))
                if validator is not None:
                    validator(payload)
                return payload, repaired, 2
            except (TypeError, ValueError) as exc:
                raise InvalidStructuredResponse(str(exc)) from exc

    @staticmethod
    def _decode_json_object(response: str) -> dict[str, Any]:
        """Strip one optional code fence and decode a single JSON object."""
        text = response.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fenced is not None:
            text = fenced.group(1).strip()
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("structured response must be a JSON object")
        return payload

    @staticmethod
    def _require_fields(payload: dict[str, Any], fields: set[str]) -> None:
        missing = sorted(fields - payload.keys())
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

    @staticmethod
    def _validate_confidence(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("confidence must be a number")
        confidence = float(value)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return confidence

    @staticmethod
    def _selected_evidence(
        payload: dict[str, Any], evidence: list[EvidenceReference]
    ) -> list[EvidenceReference]:
        raw_ids = payload.get("evidence_ids")
        if not isinstance(raw_ids, list) or not all(
            isinstance(value, str) for value in raw_ids
        ):
            raise ValueError("evidence_ids must be an array of strings")
        evidence_by_id = {item.evidence_id: item for item in evidence}
        invented = set(raw_ids) - evidence_by_id.keys()
        if invented:
            raise ValueError(f"invented evidence IDs: {', '.join(sorted(invented))}")
        return [evidence_by_id[value] for value in raw_ids]

    @staticmethod
    def _evidence_strength(evidence: list[EvidenceReference]) -> EvidenceStrength:
        kinds = {item.object_type for item in evidence}
        if len(evidence) >= 3 or ({"event", "relation"} <= kinds):
            return EvidenceStrength.STRONG
        if len(evidence) >= 2 or "event" in kinds or "relation" in kinds:
            return EvidenceStrength.MODERATE
        return EvidenceStrength.WEAK

    def _parse_plot_hole_json(
        self,
        payload: dict[str, Any],
        entity: Any,
        evidence: list[EvidenceReference],
    ) -> PlotHole | None:
        required = {
            "has_issue",
            "issue_kind",
            "description",
            "severity",
            "suggested_resolution",
            "confidence",
            "evidence_ids",
        }
        self._require_fields(payload, required)
        if not isinstance(payload["has_issue"], bool):
            raise ValueError("has_issue must be boolean")
        selected = self._selected_evidence(payload, evidence)
        confidence = self._validate_confidence(payload["confidence"])
        if not payload["has_issue"]:
            return None
        issue_kind = str(payload["issue_kind"])
        if issue_kind not in {
            "temporal_contradiction",
            "logical_conflict",
            "missing_context",
            "characterization_conflict",
        }:
            raise ValueError("invalid issue_kind")
        severity_map = {
            "high": SeverityLevel.CRITICAL,
            "medium": SeverityLevel.WARNING,
            "low": SeverityLevel.INFO,
        }
        severity_name = str(payload["severity"])
        if severity_name not in severity_map:
            raise ValueError("invalid severity")
        description = payload["description"]
        resolution = payload["suggested_resolution"]
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description must be non-empty")
        if resolution is not None and not isinstance(resolution, str):
            raise ValueError("suggested_resolution must be a string or null")
        evidence_ids = sorted(item.evidence_id for item in selected)
        fingerprint = "|".join(["plot_hole", issue_kind, entity.id, *evidence_ids])
        return PlotHole(
            issue_id=f"hole_{entity.id}_{issue_kind}",
            entity_id=entity.id,
            entity_name=entity.name,
            description=description.strip(),
            severity=severity_map[severity_name],
            suggested_resolution=resolution.strip() if resolution else None,
            confidence=confidence,
            issue_kind=issue_kind,
            evidence_strength=self._evidence_strength(selected),
            evidence=selected,
            fingerprint=fingerprint,
        )

    def _parse_relation_json(
        self,
        payload: dict[str, Any],
        source: Any,
        target: Any,
        evidence: list[EvidenceReference],
    ) -> RelationProposal | None:
        self._require_fields(
            payload,
            {
                "should_relate",
                "source_id",
                "target_id",
                "relation_type",
                "confidence",
                "reasoning",
                "evidence_ids",
            },
        )
        if not isinstance(payload["should_relate"], bool):
            raise ValueError("should_relate must be boolean")
        source_id = str(payload["source_id"])
        target_id = str(payload["target_id"])
        valid_directions = {(source.id, target.id), (target.id, source.id)}
        if (source_id, target_id) not in valid_directions:
            raise ValueError("relation direction must use the candidate IDs")
        selected = self._selected_evidence(payload, evidence)
        confidence = self._validate_confidence(payload["confidence"])
        if not payload["should_relate"]:
            return None
        relation_type = payload["relation_type"]
        reasoning = payload["reasoning"]
        if not isinstance(relation_type, str) or not relation_type.strip():
            raise ValueError("relation_type must be non-empty")
        if not isinstance(reasoning, str) or not reasoning.strip():
            raise ValueError("reasoning must be non-empty")
        by_id = {source.id: source, target.id: target}
        actual_source = by_id[source_id]
        actual_target = by_id[target_id]
        endpoint_evidence = [
            EvidenceReference(
                evidence_id=f"entity:{item.id}:endpoint",
                object_type="entity",
                object_id=item.id,
                object_name=item.name,
                field="relation_endpoint",
                excerpt=(item.description or "")[:300],
            )
            for item in (actual_source, actual_target)
        ]
        report_evidence = [*selected]
        known_evidence_ids = {item.evidence_id for item in report_evidence}
        report_evidence.extend(
            item
            for item in endpoint_evidence
            if item.evidence_id not in known_evidence_ids
        )
        fingerprint = "|".join(
            [
                "relation",
                source_id,
                target_id,
                relation_type.strip(),
                *sorted(item.evidence_id for item in selected),
            ]
        )
        return RelationProposal(
            source_id=source_id,
            source_name=actual_source.name,
            target_id=target_id,
            target_name=actual_target.name,
            suggested_relation_type=relation_type.strip(),
            reasoning=reasoning.strip(),
            confidence=confidence,
            evidence_strength=self._evidence_strength(selected),
            evidence=report_evidence,
            fingerprint=fingerprint,
        )

    def _parse_lore_json(
        self,
        payload: dict[str, Any],
        gap: Any,
        evidence: list[EvidenceReference],
    ) -> LoreGapFiller | None:
        self._require_fields(payload, {"suggestions", "evidence_ids"})
        selected = self._selected_evidence(payload, evidence)
        if {item.evidence_id for item in selected} != {
            item.evidence_id for item in evidence
        }:
            raise ValueError("lore suggestions must cite both bounding events")
        raw_suggestions = payload["suggestions"]
        if not isinstance(raw_suggestions, list):
            raise ValueError("suggestions must be an array")
        suggestions: list[ParsedLoreSuggestion] = []
        for raw in raw_suggestions:
            if not isinstance(raw, dict):
                raise ValueError("each suggestion must be an object")
            self._require_fields(raw, {"name", "date", "description"})
            if not all(isinstance(raw[key], str) for key in ("name", "date", "description")):
                raise ValueError("suggestion fields must be strings")
            if not raw["name"].strip() or not raw["description"].strip():
                raise ValueError("suggestions require a name and description")
            suggestions.append(
                ParsedLoreSuggestion(
                    name=raw["name"].strip(),
                    date_str=raw["date"].strip(),
                    description=raw["description"].strip(),
                )
            )
        if not suggestions:
            return None
        fingerprint = f"lore|{gap.start_date}|{gap.end_date}"
        return LoreGapFiller(
            gap_id=f"gap_{gap.start_date:.9f}_{gap.end_date:.9f}",
            start_date=gap.start_date,
            end_date=gap.end_date,
            suggestions=suggestions,
            evidence_strength=EvidenceStrength.MODERATE,
            evidence=selected,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _event_evidence(event: Any) -> EvidenceReference:
        return EvidenceReference(
            evidence_id=f"event:{event.id}",
            object_type="event",
            object_id=event.id,
            object_name=event.name,
            field="description",
            excerpt=(event.description or "")[:300],
            lore_date=(
                float(event.lore_date)
                if isinstance(event.lore_date, (int, float))
                else None
            ),
        )

    def _build_plot_hole_evidence(
        self,
        entity: Any,
        relations: list[dict[str, Any]],
        event_map: dict[str, Any],
        entity_name_map: dict[str, str],
    ) -> list[EvidenceReference]:
        evidence = [
            EvidenceReference(
                evidence_id=f"entity:{entity.id}:description",
                object_type="entity",
                object_id=entity.id,
                object_name=entity.name,
                field="description",
                excerpt=(entity.description or "")[:300],
            )
        ]
        for index, relation in enumerate(relations[:20]):
            relation_id = str(relation.get("id") or f"{entity.id}:{index}")
            other_id = (
                str(relation.get("source_id", ""))
                if relation.get("target_id") == entity.id
                else str(relation.get("target_id", ""))
            )
            other = event_map.get(other_id)
            evidence.append(
                EvidenceReference(
                    evidence_id=f"relation:{relation_id}",
                    object_type="relation",
                    object_id=other_id,
                    object_name=(
                        getattr(other, "name", "")
                        or entity_name_map.get(other_id, other_id)
                    ),
                    field="rel_type",
                    excerpt=str(relation.get("rel_type", "")),
                    lore_date=(
                        float(other.lore_date)
                        if other is not None
                        and isinstance(other.lore_date, (int, float))
                        else None
                    ),
                    relation_id=relation_id,
                )
            )
            if other is not None:
                evidence.append(self._event_evidence(other))
        return evidence

    @staticmethod
    def _event_ids_by_entity(
        relations: list[dict[str, Any]], events: list[Any]
    ) -> dict[str, set[str]]:
        event_ids = {event.id for event in events}
        result: dict[str, set[str]] = defaultdict(set)
        for relation in relations:
            source_id = str(relation.get("source_id", ""))
            target_id = str(relation.get("target_id", ""))
            if source_id in event_ids and target_id not in event_ids:
                result[target_id].add(source_id)
            if target_id in event_ids and source_id not in event_ids:
                result[source_id].add(target_id)
        return result

    @staticmethod
    def _linked_ids_by_entity(entities: list[Any]) -> dict[str, set[str]]:
        result: dict[str, set[str]] = defaultdict(set)
        known_ids = {entity.id for entity in entities}
        for entity in entities:
            for link in WikiLinkParser.extract_links(entity.description or ""):
                if link.target_id in known_ids:
                    result[entity.id].add(str(link.target_id))
        return result

    def _build_relation_evidence(
        self,
        source: Any,
        target: Any,
        event_ids_by_entity: dict[str, set[str]],
        linked_ids_by_entity: dict[str, set[str]],
        events: list[Any],
    ) -> list[EvidenceReference]:
        evidence: list[EvidenceReference] = []
        shared_tags = sorted(
            set(source.attributes.get("_tags", []))
            & set(target.attributes.get("_tags", []))
        )
        for tag in shared_tags:
            evidence.append(
                EvidenceReference(
                    evidence_id=f"tag:{source.id}:{target.id}:{tag}",
                    object_type="tag",
                    object_id=source.id,
                    object_name=tag,
                    field="tags",
                    excerpt=f"Shared tag: {tag}",
                )
            )
        event_map = {event.id: event for event in events}
        shared_events = sorted(
            event_ids_by_entity.get(source.id, set())
            & event_ids_by_entity.get(target.id, set())
        )
        evidence.extend(
            self._event_evidence(event_map[event_id])
            for event_id in shared_events
            if event_id in event_map
        )
        for owner, linked in ((source, target), (target, source)):
            if linked.id in linked_ids_by_entity.get(owner.id, set()):
                evidence.append(
                    EvidenceReference(
                        evidence_id=f"link:{owner.id}:{linked.id}",
                        object_type="entity",
                        object_id=owner.id,
                        object_name=owner.name,
                        field="description",
                        excerpt=f"ID-based link to {linked.name}",
                    )
                )
        return evidence

    def _execute_tasks(
        self,
        tasks: dict[str, Any],
        on_partial: Callable[[str, Any], None] | None,
        is_cancelled: CancellationCheck,
    ) -> dict[str, Any]:
        """Run independent sub-analyses and stream successful results."""
        results: dict[str, Any] = {}
        if not tasks:
            return results

        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            future_to_name = {pool.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                    self._raise_if_cancelled(is_cancelled)
                    if on_partial is not None:
                        result = results[name]
                        on_partial(name, result[:3] if name == "lore" else result[:2])
                except IntelligenceAnalysisCancelled:
                    for pending in future_to_name:
                        pending.cancel()
                    raise
                except Exception as exc:
                    logger.error("Sub-analysis %r failed: %s", name, exc)
                    failure = AnalysisCoverage(
                        eligible=1,
                        attempted=1,
                        failed=1,
                        errors=[str(exc)],
                    )
                    audit = [
                        self._make_audit_entry(
                            f"{name}_analysis",
                            error=str(exc),
                        )
                    ]
                    results[name] = (
                        ([], audit, None, failure)
                        if name == "lore"
                        else ([], audit, failure)
                    )
        return results

    @staticmethod
    def _raise_if_cancelled(is_cancelled: CancellationCheck) -> None:
        """Raise the cooperative cancellation exception when requested."""
        if is_cancelled():
            raise IntelligenceAnalysisCancelled()

    def _make_audit_entry(
        self,
        entry_type: str,
        *,
        model: str | None = None,
        error: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Build a standardized audit log entry.

        Args:
            entry_type: Sub-analyzer label, e.g. ``"plot_hole_detection"``.
            model: LLM model identifier; present on success entries.
            error: Error message string; present on failure entries.
            **extra: Additional key/value pairs specific to the entry type
                (e.g. ``entity_id``, ``source_id``, ``gap_start``).

        Returns:
            dict[str, Any]: Audit entry ready to append to the audit log.
        """
        entry: dict[str, Any] = {"type": entry_type, "timestamp": time.time(), **extra}
        if model is not None:
            entry["model"] = model
        if error is not None:
            entry["error"] = error
        return entry

    def _find_relation_candidates(
        self,
        entities: list[Any],
        event_ids_by_entity: dict[str, set[str]] | None = None,
        linked_ids_by_entity: dict[str, set[str]] | None = None,
    ) -> list[tuple[Any, Any]]:
        """Find entity pairs sharing tags, events, or explicit ID links.

        Uses a tag → entity index for O(T) grouping instead of O(E²) pairs.

        Args:
            entities: All entities in the world.

        Returns:
            list[tuple]: Unsorted list of (source, target) pairs.
        """
        tag_to_entities: dict[str, list[Any]] = defaultdict(list)
        for entity in entities:
            for tag in entity.attributes.get("_tags", []):
                tag_to_entities[tag].append(entity)

        candidates: list[tuple[Any, Any]] = []
        seen: set[frozenset[str]] = set()
        for group in tag_to_entities.values():
            for i, e1 in enumerate(group):
                for e2 in group[i + 1 :]:
                    key = frozenset((e1.id, e2.id))
                    if key not in seen:
                        seen.add(key)
                        candidates.append((e1, e2))
        event_map = event_ids_by_entity or {}
        link_map = linked_ids_by_entity or {}
        for index, first in enumerate(entities):
            for second in entities[index + 1 :]:
                key = frozenset((first.id, second.id))
                if key in seen:
                    continue
                shared_event = bool(
                    event_map.get(first.id, set()) & event_map.get(second.id, set())
                )
                linked = (
                    second.id in link_map.get(first.id, set())
                    or first.id in link_map.get(second.id, set())
                )
                if shared_event or linked:
                    seen.add(key)
                    candidates.append((first, second))
        return candidates

    def _get_provider(self) -> Provider:
        """Return the injected provider or create one from application settings.

        Returns:
            Provider: A configured LLM provider instance.
        """
        if self._provider is not None:
            return self._provider

        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
        from src.services.llm_provider import create_provider

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        provider_id = str(settings.value("ai_provider", "lmstudio"))
        return create_provider(provider_id)
