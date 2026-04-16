"""Intelligence Analyzer Service.

AI-powered world analysis using RAG + LLM.  Detects plot holes in entity
narratives, infers missing relations between entities that share context,
and generates lore suggestions to fill timeline gaps.

All LLM calls are isolated per sub-analyzer so a single provider failure
does not prevent the others from running.  Each interaction is recorded in
the ``audit_log`` of the returned :class:`~src.core.analysis.IntelligenceReport`.

The three sub-analyses (plot_holes, relations, lore) are independent and run
concurrently via :class:`~concurrent.futures.ThreadPoolExecutor`.  All database
reads are pre-fetched on the calling thread so the ``DatabaseService`` SQLite
connection is never accessed from a worker thread.  Each task receives its own
:class:`~src.services.llm_provider.Provider` instance so that ``CircuitBreaker``
state is not shared across threads.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import TYPE_CHECKING, Any, Callable

from src.core.analysis import (
    IntelligenceReport,
    LoreGapFiller,
    ParsedLoreSuggestion,
    PlotHole,
    RelationProposal,
    SeverityLevel,
)
from src.core.calendar import CalendarConverter
from src.services.temporal_analyzer import TemporalAnalyzer

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService
    from src.services.llm_provider import Provider

logger = logging.getLogger(__name__)


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
    """AI-powered world analysis using RAG + LLM.

    Analyses the world database for three categories of insight:

    - **Plot holes**: Narrative inconsistencies in the top-connected entities,
      detected by asking an LLM to review each entity's temporal and relational
      context.
    - **Relation proposals**: Missing relations between entities that share tags
      or other contextual signals, inferred by the LLM.
    - **Lore suggestions**: Generated bridging events for timeline gaps detected
      by :class:`~src.services.temporal_analyzer.TemporalAnalyzer`.

    Args:
        db_service: A connected
            :class:`~src.services.db_service.DatabaseService` instance.
        provider: Optional pre-built :class:`~src.services.llm_provider.Provider`
            instance.  When ``None`` (default) the analyzer creates one from
            the application's QSettings on first use.  Pass an explicit provider
            in tests to avoid real LLM calls.
    """

    def __init__(
        self,
        db_service: DatabaseService,
        provider: Provider | None = None,
    ) -> None:
        """Initialize the analyzer.

        Args:
            db_service: A connected DatabaseService instance.
            provider: Optional injectable provider.  Pass a pre-built
                :class:`~src.services.llm_provider.Provider` in tests to avoid
                real LLM calls; leave ``None`` in production to auto-select from
                application settings.
        """
        self.db_service = db_service
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        analysis_type: str = "all",
        on_partial: Callable[[str, Any], None] | None = None,
    ) -> IntelligenceReport:
        """Run AI analysis and return an :class:`~src.core.analysis.IntelligenceReport`.

        All database reads are performed on the calling thread before any worker
        threads are spawned.  The three sub-analyses then run concurrently in a
        :class:`~concurrent.futures.ThreadPoolExecutor`; each receives its own
        :class:`~src.services.llm_provider.Provider` instance so ``CircuitBreaker``
        state is not shared across threads.

        Args:
            analysis_type: Controls which sub-analyses run.  One of
                ``"all"`` | ``"plot_holes"`` | ``"relations"`` | ``"lore"``.
                Unknown values run all three.
            on_partial: Optional callback invoked on the calling thread as each
                sub-analysis completes, before the final report is returned.
                Called with ``(result_type, raw_result)`` where *result_type* is
                ``"holes"``, ``"relations"``, or ``"lore"`` and *raw_result* is
                the tuple returned by that sub-analyzer.  Not called for failed
                sub-analyses.

        Returns:
            IntelligenceReport: Populated report.  Sub-sections that were not
            requested are empty lists.
        """
        # ------------------------------------------------------------------
        # Phase 1: pre-fetch all DB data on the calling thread.
        # ThreadPoolExecutor workers must not touch db_service — the SQLite
        # connection is not safe to share across threads without check_same_thread=False.
        # ------------------------------------------------------------------
        entities = self.db_service.get_all_entities()
        relations = self.db_service.get_all_relations()
        events = self.db_service.get_all_events()

        temporal_report: Any | None = None
        if analysis_type in ("all", "lore"):
            temporal_report = TemporalAnalyzer(self.db_service).analyze()

        # ------------------------------------------------------------------
        # Phase 2: build tasks.  Each task gets its own provider so that
        # CircuitBreaker mutable state is not shared across threads.
        # functools.partial binds the provider immediately — no closure-capture bug.
        # ------------------------------------------------------------------
        tasks: dict[str, Any] = {}

        if analysis_type in ("all", "plot_holes"):
            tasks["holes"] = partial(
                self._detect_plot_holes,
                self._get_provider(),
                entities,
                relations,
                events,
            )

        if analysis_type in ("all", "relations"):
            tasks["relations"] = partial(
                self._infer_relations,
                self._get_provider(),
                entities,
                relations,
            )

        if analysis_type in ("all", "lore") and temporal_report is not None:
            tasks["lore"] = partial(
                self._generate_lore,
                self._get_provider(),
                temporal_report,
                events,
            )

        # Derive model name from first provider before threads start.
        model_name = "unknown"
        if tasks:
            # Peek at metadata via a temporary provider (cheap — no API call).
            model_name = self._get_provider().metadata().get("generation_model", "unknown")

        # ------------------------------------------------------------------
        # Phase 3: run sub-analyses concurrently.
        # ------------------------------------------------------------------
        results: dict[str, Any] = {}
        if tasks:
            with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
                future_to_name = {pool.submit(fn): name for name, fn in tasks.items()}
                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        results[name] = future.result()
                        if on_partial is not None:
                            on_partial(name, results[name])
                    except Exception as exc:
                        logger.error("Sub-analysis %r failed: %s", name, exc)
                        results[name] = None

        # ------------------------------------------------------------------
        # Phase 4: collect results.
        # ------------------------------------------------------------------
        plot_holes: list[PlotHole] = []
        relation_proposals: list[RelationProposal] = []
        lore_suggestions: list[LoreGapFiller] = []
        audit_log: list[dict[str, Any]] = []
        calendar_config: Any | None = None

        if results.get("holes") is not None:
            holes, holes_audit = results["holes"]
            plot_holes.extend(holes)
            audit_log.extend(holes_audit)

        if results.get("relations") is not None:
            proposals, rel_audit = results["relations"]
            relation_proposals.extend(proposals)
            audit_log.extend(rel_audit)

        if results.get("lore") is not None:
            suggestions, lore_audit, calendar_config = results["lore"]
            lore_suggestions.extend(suggestions)
            audit_log.extend(lore_audit)

        return IntelligenceReport(
            timestamp=time.time(),
            plot_holes=plot_holes,
            relation_proposals=relation_proposals,
            lore_suggestions=lore_suggestions,
            analysis_model=model_name,
            audit_log=audit_log,
            calendar_config=calendar_config,
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
    ) -> tuple[list[PlotHole], list[dict[str, Any]]]:
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

        Returns:
            tuple: ``(plot_holes, audit_log)`` where *plot_holes* is a list
            of :class:`~src.core.analysis.PlotHole` objects and *audit_log*
            contains one dict per LLM call (or error).
        """
        audit_log: list[dict[str, Any]] = []
        plot_holes: list[PlotHole] = []

        if not entities:
            return plot_holes, audit_log

        # Count relations per entity (source or target)
        relation_count: dict[str, int] = defaultdict(int)
        for rel in relations:
            relation_count[rel.get("source_id", "")] += 1
            relation_count[rel.get("target_id", "")] += 1

        top_entities = sorted(
            entities,
            key=lambda e: relation_count[e.id],
            reverse=True,
        )[:_MAX_ENTITIES_FOR_PLOT_HOLES]

        event_map = {e.id: e for e in events}
        entity_name_map: dict[str, str] = {e.id: e.name for e in entities}
        relations_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            relations_by_entity[rel.get("source_id", "")].append(rel)
            relations_by_entity[rel.get("target_id", "")].append(rel)

        for entity in top_entities:
            prompt = self._build_plot_hole_prompt(
                entity,
                relations_by_entity[entity.id],
                event_map,
                entity_name_map,
            )
            try:
                result = provider.generate(prompt)
                response_text = result.get("text", "")
                audit_log.append(
                    self._make_audit_entry(
                        "plot_hole_detection",
                        model=result.get("model", "unknown"),
                        entity_id=entity.id,
                        prompt_length=len(prompt),
                        response_length=len(response_text),
                    )
                )
                plot_holes.extend(self._parse_plot_holes(response_text, entity))
            except Exception as exc:
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

        return plot_holes, audit_log

    def _infer_relations(
        self,
        provider: Provider,
        entities: list[Any],
        relations: list[dict[str, Any]],
    ) -> tuple[list[RelationProposal], list[dict[str, Any]]]:
        """Infer missing relations between entity pairs that share context.

        Candidate pairs are entities sharing at least one tag.  Pairs that
        already have an existing relation in either direction are skipped.
        At most :data:`_MAX_RELATION_CANDIDATES` pairs are evaluated.

        Args:
            provider: The LLM provider to use.
            entities: All entities in the world (pre-fetched by caller).
            relations: All relations in the world (pre-fetched by caller).

        Returns:
            tuple: ``(proposals, audit_log)``.
        """
        audit_log: list[dict[str, Any]] = []
        proposals: list[RelationProposal] = []

        if not entities:
            return proposals, audit_log

        existing_pairs: set[tuple[str, str]] = {
            (rel.get("source_id", ""), rel.get("target_id", ""))
            for rel in relations
        }

        candidates = self._find_relation_candidates(entities)[:_MAX_RELATION_CANDIDATES]

        for source, target in candidates:
            if (source.id, target.id) in existing_pairs:
                continue
            if (target.id, source.id) in existing_pairs:
                continue

            prompt = self._build_relation_inference_prompt(source, target)
            try:
                result = provider.generate(prompt)
                response_text = result.get("text", "")
                audit_log.append(
                    self._make_audit_entry(
                        "relation_inference",
                        model=result.get("model", "unknown"),
                        source_id=source.id,
                        target_id=target.id,
                    )
                )
                proposal = self._parse_relation_proposal(response_text, source, target)
                if proposal is not None:
                    proposals.append(proposal)
            except Exception as exc:
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

        return proposals, audit_log

    def _generate_lore(
        self,
        provider: Provider,
        temporal_report: Any,
        events: list[Any],
    ) -> tuple[list[LoreGapFiller], list[dict[str, Any]], Any | None]:
        """Generate bridging lore suggestions for timeline gaps.

        Uses a pre-computed :class:`~src.services.temporal_analyzer.TemporalAnalysisReport`
        and pre-fetched events so this method performs no database access and
        is safe to run in a worker thread.

        Args:
            provider: The LLM provider to use.
            temporal_report: Pre-computed temporal analysis report from the
                calling thread (contains timeline gaps and calendar config).
            events: All events in the world (pre-fetched by caller).

        Returns:
            tuple: ``(suggestions, audit_log, calendar_config)`` where
            *calendar_config* is forwarded from the temporal report so the
            caller can attach it to the returned
            :class:`~src.core.analysis.IntelligenceReport`.
        """
        audit_log: list[dict[str, Any]] = []
        suggestions: list[LoreGapFiller] = []

        calendar_config = temporal_report.calendar_config
        gaps = temporal_report.timeline_gaps[:_MAX_GAPS_FOR_LORE]
        if not gaps:
            return suggestions, audit_log, calendar_config

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
            events_before = [e for e in sorted_events if e.lore_date <= gap.start_date]
            events_after = [e for e in sorted_events if e.lore_date >= gap.end_date]

            if not events_before or not events_after:
                continue

            prompt = self._build_lore_generation_prompt(
                gap, events_before[-1], events_after[0], converter
            )
            try:
                result = provider.generate(prompt)
                response_text = result.get("text", "")
                audit_log.append(
                    self._make_audit_entry(
                        "lore_generation",
                        model=result.get("model", "unknown"),
                        gap_start=gap.start_date,
                        gap_end=gap.end_date,
                    )
                )
                filler = self._parse_lore_suggestions(response_text, gap)
                if filler is not None:
                    suggestions.append(filler)
            except Exception as exc:
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

        return suggestions, audit_log, calendar_config

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_plot_hole_prompt(
        self,
        entity: Any,
        entity_relations: list[dict[str, Any]],
        event_map: dict[str, Any],
        entity_name_map: dict[str, str],
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
        return (
            f"Analyse this character/location for logical inconsistencies or plot holes:\n\n"
            f"Name: {entity.name}\n"
            f"Type: {getattr(entity, 'type', 'Unknown')}\n"
            f"Description: {entity.description or 'None'}\n\n"
            f"Relations use directed notation: A --relation--> B means A [relation] B.\n"
            f"Relations:\n{rel_lines or '(none)'}\n\n"
            f"Identify any timeline contradictions, logical impossibilities, "
            f"missing context, or inconsistent characterization.\n\n"
            f"Format each issue as:\n"
            f"PLOT HOLE: [description]\n"
            f"SEVERITY: [high/medium/low]\n"
            f"RESOLUTION: [suggested fix]\n"
            f"CONFIDENCE: [0-1]\n"
        )

    def _build_relation_inference_prompt(self, source: Any, target: Any) -> str:
        """Build a relation inference prompt for an entity pair.

        Args:
            source: Source entity.
            target: Target entity.

        Returns:
            str: Formatted prompt string.
        """
        return (
            f"Should these two entities have a direct relation?\n\n"
            f"{source.name} ({getattr(source, 'type', 'unknown')})\n"
            f"Description: {source.description or 'None'}\n"
            f"Tags: {source.attributes.get('_tags', [])}\n\n"
            f"{target.name} ({getattr(target, 'type', 'unknown')})\n"
            f"Description: {target.description or 'None'}\n"
            f"Tags: {target.attributes.get('_tags', [])}\n\n"
            f"Relations use directed notation: SOURCE --RELATION_TYPE--> TARGET means "
            f"SOURCE [RELATION_TYPE] TARGET. Use active-voice relation types "
            f"(e.g. 'employs' not 'employed_by', 'governs' not 'governed_by').\n\n"
            f"Answer format:\n"
            f"SHOULD_RELATE: [yes/no]\n"
            f"SOURCE: [name of the source entity]\n"
            f"TARGET: [name of the target entity]\n"
            f"RELATION_TYPE: [active-voice type]\n"
            f"CONFIDENCE: [0-1]\n"
            f"REASONING: [why]\n"
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
        return (
            f"There is a {gap_years}-year gap in the timeline.\n\n"
            f"Last event: Year {before_year} — {before_event.name}\n"
            f"Description: {before_event.description or 'None'}\n\n"
            f"Next event: Year {after_year} — {after_event.name}\n"
            f"Description: {after_event.description or 'None'}\n\n"
            f"Generate 2-3 plausible bridging events.\n\n"
            f"Format each as:\n"
            f"EVENT: [name]\n"
            f"DATE: [estimated year]\n"
            f"DESCRIPTION: [brief description]\n"
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

    def _find_relation_candidates(self, entities: list[Any]) -> list[tuple[Any, Any]]:
        """Find entity pairs that share at least one tag.

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
