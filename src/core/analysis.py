"""Analysis data models for Tier 1 features.

Defines dataclasses for world validation, temporal analysis, and intelligence
suite results. These are pure data containers — no database or service
dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SeverityLevel(Enum):
    """Issue severity for user prioritization.

    Attributes:
        CRITICAL: Data integrity risk; must be resolved.
        WARNING: Quality issue; should be reviewed.
        INFO: Suggestion; consider acting on it.
    """

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueType(Enum):
    """Categorized issue types for filtering.

    Attributes:
        ORPHANED_ENTITY: Entity with no relations and no mentions.
        BROKEN_REFERENCE: Relation pointing to a non-existent object.
        INCOMPLETE_ENTITY: Entity with minimal or missing description.
        INCOMPLETE_EVENT: Event with minimal or missing description.
        ORPHANED_RELATION: Relation not connected to any valid path.
        TAG_UNUSED: Tag used in fewer than two items.
        MISSING_RELATION: Expected relation is absent.
    """

    ORPHANED_ENTITY = "orphaned_entity"
    BROKEN_REFERENCE = "broken_reference"
    INCOMPLETE_ENTITY = "incomplete_entity"
    INCOMPLETE_EVENT = "incomplete_event"
    ORPHANED_RELATION = "orphaned_relation"
    TAG_UNUSED = "tag_unused"
    MISSING_RELATION = "missing_relation"


# ---------------------------------------------------------------------------
# Feature 1: World Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """Single validation issue found during world consistency check.

    Attributes:
        severity: How serious the issue is.
        issue_type: Categorized type for filtering.
        object_id: ID of the problematic object.
        object_type: One of "entity", "event", "relation", or "tag".
        object_name: Human-readable name for display.
        message: Human-readable description of the problem.
        suggestion: Optional actionable fix suggestion.
        related_ids: IDs of related objects for UI drill-down.
    """

    severity: SeverityLevel
    issue_type: IssueType
    object_id: str
    object_type: str
    object_name: str
    message: str
    suggestion: str | None = None
    related_ids: list[str] | None = None

    def __post_init__(self) -> None:
        """Normalize related_ids to an empty list when not provided."""
        if self.related_ids is None:
            self.related_ids = []


@dataclass
class CompletenessScore:
    """Per-object completeness metrics.

    Score components: description (40%), tags (20%), relations (20%),
    image (10%). Maximum score is 90 (the "type" component is not yet
    automated). Call ``calculate_score()`` to compute the current value;
    ``completeness_score`` is a placeholder for an externally cached result.

    Attributes:
        object_id: ID of the entity or event.
        object_type: "entity" or "event".
        name: Display name.
        has_description: Whether any description exists.
        description_length: Character count of description.
        has_image: Whether an image attachment exists.
        has_tags: Whether any tags are assigned.
        tag_count: Number of assigned tags.
        relation_count: Number of relations involving this object.
        completeness_score: Externally supplied or cached score value.
            Prefer calling ``calculate_score()`` for a live computation.
    """

    object_id: str
    object_type: str
    name: str
    has_description: bool
    description_length: int
    has_image: bool
    has_tags: bool
    tag_count: int
    relation_count: int
    completeness_score: float

    def calculate_score(self) -> float:
        """Compute and return a 0–100 completeness score from current fields.

        Score components:
            - Description length > 50 chars: 40 pts; > 0 chars: 20 pts.
            - Tags: 5 pts each, capped at 20.
            - Relations: 5 pts each, capped at 20.
            - Image: 10 pts.

        Returns:
            float: Score from 0.0 to 100.0.
        """
        score = 0.0

        if self.description_length > 50:
            score += 40
        elif self.description_length > 0:
            score += 20

        if self.has_tags:
            score += min(20.0, self.tag_count * 5.0)

        if self.relation_count > 0:
            score += min(20.0, self.relation_count * 5.0)

        if self.has_image:
            score += 10

        return min(100.0, score)


@dataclass
class WorldValidationReport:
    """Complete validation report for an entire world.

    Attributes:
        timestamp: Unix timestamp when the report was generated.
        total_entities: Number of entities in the world.
        total_events: Number of events in the world.
        total_relations: Number of relations in the world.
        total_tags: Number of tags in the world.
        issues: All detected validation issues.
        issues_by_severity: Mapping of SeverityLevel → count.
        issues_by_type: Mapping of issue_type string value → count.
        completeness_scores: Per-object completeness metrics.
        average_completeness: Mean completeness score across all objects.
        orphaned_entities_count: Count of orphaned entity issues.
        broken_references_count: Count of broken reference issues.
        unused_tags_count: Count of unused tag issues.
    """

    timestamp: float
    total_entities: int
    total_events: int
    total_relations: int
    total_tags: int
    issues: list[ValidationIssue]
    issues_by_severity: dict[SeverityLevel, int]
    issues_by_type: dict[str, int]
    completeness_scores: list[CompletenessScore]
    average_completeness: float
    orphaned_entities_count: int
    broken_references_count: int
    unused_tags_count: int

    def get_issues_by_severity(self, severity: SeverityLevel) -> list[ValidationIssue]:
        """Return all issues matching the given severity.

        Args:
            severity: The severity level to filter by.

        Returns:
            list[ValidationIssue]: Filtered list of matching issues.
        """
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_type(self, issue_type: IssueType) -> list[ValidationIssue]:
        """Return all issues matching the given type.

        Args:
            issue_type: The issue type to filter by.

        Returns:
            list[ValidationIssue]: Filtered list of matching issues.
        """
        return [i for i in self.issues if i.issue_type == issue_type]


# ---------------------------------------------------------------------------
# Feature 2: Temporal Analysis
# ---------------------------------------------------------------------------


@dataclass
class TimelineGap:
    """A period with no events.

    Attributes:
        start_date: Float lore_date of the event before the gap.
        end_date: Float lore_date of the event after the gap.
        gap_duration: Duration of the gap in lore time units.
        message: Human-readable description.
        affected_entity_ids: Entities whose timelines span this gap.
    """

    start_date: float
    end_date: float
    gap_duration: float
    message: str = ""
    affected_entity_ids: list[str] = field(default_factory=list)


@dataclass
class TemporalConflict:
    """A temporal logic violation.

    Attributes:
        conflict_type: One of "lifespan_violation", "invalid_relation_window",
            or "state_contradiction".
        entity_id: ID of the conflicting entity or relation.
        entity_name: Display name.
        problem_date: The lore_date where the conflict occurs.
        message: Human-readable description.
        suggestion: Optional fix suggestion.
        severity: How serious the conflict is.
    """

    conflict_type: str
    entity_id: str
    entity_name: str
    problem_date: float | None
    message: str
    suggestion: str | None = None
    severity: SeverityLevel = SeverityLevel.WARNING


@dataclass
class CharacterLifespan:
    """Computed lifespan for a character entity.

    Attributes:
        entity_id: ID of the character entity.
        entity_name: Display name.
        birth_date: Optional lore_date of birth.
        death_date: Optional lore_date of death.
        life_span_years: Computed lifespan duration, or None if unknown.
        violating_events: Event IDs that occur outside this lifespan.
    """

    entity_id: str
    entity_name: str
    birth_date: float | None
    death_date: float | None
    life_span_years: float | None
    violating_events: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Return True if birth and death dates are logically consistent.

        Both dates must be set for a violation to be detectable. When both
        are present, birth_date must be strictly less than death_date —
        equal dates are also considered invalid.

        Returns:
            bool: True when birth_date < death_date, or either date is None.
        """
        if self.birth_date is not None and self.death_date is not None:
            return self.birth_date < self.death_date
        return True


@dataclass
class TemporalAnalysisReport:
    """Full temporal analysis report.

    Attributes:
        timestamp: Unix timestamp when the report was generated.
        timeline_gaps: Detected periods with no events.
        total_gap_duration: Sum of all gap durations.
        conflicts: Detected temporal logic violations.
        character_lifespans: Computed lifespans for character entities.
        earliest_event_date: Lore date of the earliest event.
        latest_event_date: Lore date of the latest event.
        calendar_name: Name of the active calendar used for display.
    """

    timestamp: float
    timeline_gaps: list[TimelineGap]
    total_gap_duration: float
    conflicts: list[TemporalConflict]
    character_lifespans: list[CharacterLifespan]
    earliest_event_date: float | None
    latest_event_date: float | None
    calendar_name: str
    calendar_config: Any | None = None


# ---------------------------------------------------------------------------
# Feature 3: Intelligence Suite
# ---------------------------------------------------------------------------


@dataclass
class PlotHole:
    """A detected plot hole or narrative inconsistency.

    Attributes:
        issue_id: Unique identifier for this plot hole.
        entity_id: ID of the entity the plot hole concerns.
        entity_name: Display name.
        description: What the inconsistency is.
        severity: How serious the issue is.
        suggested_resolution: Optional suggested fix.
        confidence: Model confidence score from 0.0 to 1.0.
    """

    issue_id: str
    entity_id: str
    entity_name: str
    description: str
    severity: SeverityLevel
    suggested_resolution: str | None = None
    confidence: float = 0.8


@dataclass
class RelationProposal:
    """A suggested relation between two entities.

    Attributes:
        source_id: ID of the source entity.
        source_name: Display name of source.
        target_id: ID of the target entity.
        target_name: Display name of target.
        suggested_relation_type: Proposed relation type string.
        reasoning: Why this relation is suggested.
        confidence: Model confidence score from 0.0 to 1.0.
    """

    source_id: str
    source_name: str
    target_id: str
    target_name: str
    suggested_relation_type: str
    reasoning: str
    confidence: float = 0.7


@dataclass
class ParsedLoreSuggestion:
    """One bridging-event suggestion from the LLM.

    Attributes:
        name: Event title.
        date_str: Estimated date string (e.g. "Approximately Year 1580").
        description: Brief event description.
    """

    name: str
    date_str: str
    description: str


@dataclass
class LoreGapFiller:
    """Generated lore suggestions to fill a timeline gap.

    Attributes:
        gap_id: Identifier for the gap being filled.
        start_date: Gap start in lore time.
        end_date: Gap end in lore time.
        suggestions: List of plausible event descriptions.
        selected_suggestion: Index of user-selected suggestion, or None.
    """

    gap_id: str
    start_date: float
    end_date: float
    suggestions: list[ParsedLoreSuggestion]
    selected_suggestion: int | None = None


@dataclass
class IntelligenceReport:
    """Full AI analysis report.

    Attributes:
        timestamp: Unix timestamp when the report was generated.
        plot_holes: Detected plot holes and inconsistencies.
        relation_proposals: Suggested new relations.
        lore_suggestions: Generated lore for timeline gaps.
        analysis_model: Identifier of the LLM used.
        audit_log: List of raw LLM interaction records.
    """

    timestamp: float
    plot_holes: list[PlotHole]
    relation_proposals: list[RelationProposal]
    lore_suggestions: list[LoreGapFiller]
    analysis_model: str
    audit_log: list[dict[str, Any]]
    calendar_config: Any | None = None
