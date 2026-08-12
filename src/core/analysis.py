"""Analysis data models for Tier 1 features.

Defines dataclasses for world validation, temporal analysis, and intelligence
suite results. These are pure data containers — no database or service
dependencies.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnalysisScopeKind(Enum):
    """Supported boundaries for an AI analysis run."""

    WHOLE_WORLD = "whole_world"
    CURRENT_ITEM = "current_item"
    SELECTION = "selection"
    TAGS = "tags"
    DATE_RANGE = "date_range"


class AnalysisPreset(Enum):
    """Request budgets available to users."""

    QUICK = "quick"
    BALANCED = "balanced"
    THOROUGH = "thorough"

    @property
    def limits(self) -> dict[str, int]:
        """Return plot-hole, relation, and lore candidate limits."""
        return {
            AnalysisPreset.QUICK: {"plot_holes": 3, "relations": 5, "lore": 2},
            AnalysisPreset.BALANCED: {
                "plot_holes": 6,
                "relations": 10,
                "lore": 3,
            },
            AnalysisPreset.THOROUGH: {
                "plot_holes": 10,
                "relations": 20,
                "lore": 5,
            },
        }[self]


class AnalysisSectionStatus(Enum):
    """Lifecycle state for one analysis section."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class EvidenceStrength(Enum):
    """Deterministic strength of evidence supplied to an AI finding."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class AnalysisScope:
    """Serializable boundary for an AI analysis run."""

    kind: AnalysisScopeKind = AnalysisScopeKind.WHOLE_WORLD
    item_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    start_date: float | None = None
    end_date: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe scope payload."""
        return {
            "kind": self.kind.value,
            "item_ids": list(self.item_ids),
            "tags": list(self.tags),
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AnalysisScope":
        """Build a scope from a serialized payload."""
        if not data:
            return cls()
        try:
            kind = AnalysisScopeKind(str(data.get("kind", "whole_world")))
        except ValueError:
            kind = AnalysisScopeKind.WHOLE_WORLD
        return cls(
            kind=kind,
            item_ids=[str(value) for value in data.get("item_ids", [])],
            tags=[str(value) for value in data.get("tags", [])],
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )


@dataclass
class AnalysisCoverage:
    """Coverage and request counts for one analysis section."""

    eligible: int = 0
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    requests: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> AnalysisSectionStatus:
        """Derive an honest terminal status from coverage counts."""
        if self.eligible == 0:
            return AnalysisSectionStatus.SKIPPED
        if self.succeeded == 0 and self.failed > 0:
            return AnalysisSectionStatus.FAILED
        if self.failed > 0:
            return AnalysisSectionStatus.PARTIAL
        return AnalysisSectionStatus.COMPLETE


@dataclass
class EvidenceReference:
    """Stable reference to world data supporting a finding."""

    evidence_id: str
    object_type: str
    object_id: str
    object_name: str
    field: str = ""
    excerpt: str = ""
    lore_date: float | None = None
    relation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe evidence payload."""
        return {
            "evidence_id": self.evidence_id,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "object_name": self.object_name,
            "field": self.field,
            "excerpt": self.excerpt,
            "lore_date": self.lore_date,
            "relation_id": self.relation_id,
        }


@dataclass
class CompletenessComponent:
    """One transparent component of a documentation score."""

    name: str
    earned: float
    maximum: float
    explanation: str


@dataclass
class CompletenessBreakdown:
    """Transparent component breakdown for one object."""

    components: list[CompletenessComponent] = field(default_factory=list)

    @property
    def earned(self) -> float:
        """Return total earned points."""
        return sum(component.earned for component in self.components)

    @property
    def maximum(self) -> float:
        """Return total available points."""
        return sum(component.maximum for component in self.components)


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
    BROKEN_WIKILINK = "broken_wikilink"
    AMBIGUOUS_WIKILINK = "ambiguous_wikilink"
    DUPLICATE_RELATION = "duplicate_relation"
    MISSING_ASSET = "missing_asset"
    UNSAFE_ASSET_PATH = "unsafe_asset_path"
    ORPHANED_ATTACHMENT = "orphaned_attachment"
    INVALID_DATE = "invalid_date"
    INVALID_DURATION = "invalid_duration"
    INVALID_TEMPORAL_WINDOW = "invalid_temporal_window"


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
    evidence: list[EvidenceReference] = field(default_factory=list)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        """Normalize related_ids to an empty list when not provided."""
        if self.related_ids is None:
            self.related_ids = []


@dataclass
class CompletenessScore:
    """Per-object completeness metrics.

    Uses a transparent 100-point documentation profile tailored to entities
    and events. Call :meth:`calculate_score` to populate :attr:`breakdown`
    and return the current value.

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
    has_name: bool = False
    has_type: bool = False
    has_valid_date: bool = False
    breakdown: CompletenessBreakdown = field(default_factory=CompletenessBreakdown)

    def calculate_score(self) -> float:
        """Compute and return the object's 0–100 documentation score."""
        is_event = self.object_type == "event"
        weights = (
            {
                "name": 10.0,
                "type": 10.0,
                "date": 20.0,
                "description": 40.0,
                "tags": 5.0,
                "relations": 10.0,
                "attachment": 5.0,
            }
            if is_event
            else {
                "name": 10.0,
                "type": 15.0,
                "description": 45.0,
                "tags": 10.0,
                "relations": 15.0,
                "attachment": 5.0,
            }
        )

        description_weight = weights["description"]
        description_earned = 0.0
        if self.description_length >= 50:
            description_earned = description_weight
        elif self.description_length > 0:
            description_earned = description_weight / 2.0

        values: list[tuple[str, float, bool, str]] = [
            ("Name", weights["name"], self.has_name, "A non-empty name."),
            ("Type", weights["type"], self.has_type, "A non-empty object type."),
        ]
        if is_event:
            values.append(
                (
                    "Lore date",
                    weights["date"],
                    self.has_valid_date,
                    "A finite lore date.",
                )
            )
        values.extend(
            [
                (
                    "Tags",
                    weights["tags"],
                    self.has_tags,
                    "At least one organizational tag.",
                ),
                (
                    "Relations",
                    weights["relations"],
                    self.relation_count > 0,
                    "At least one connected relation.",
                ),
                (
                    "Attachment",
                    weights["attachment"],
                    self.has_image,
                    "At least one image attachment.",
                ),
            ]
        )
        components = [
            CompletenessComponent(name, maximum if present else 0.0, maximum, text)
            for name, maximum, present, text in values
        ]
        components.insert(
            2,
            CompletenessComponent(
                "Description",
                description_earned,
                description_weight,
                "Half credit below 50 trimmed characters; full credit at 50 or more.",
            ),
        )
        self.breakdown = CompletenessBreakdown(components)
        return min(100.0, self.breakdown.earned)


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
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    snapshot_timestamp: float | None = None
    scope: AnalysisScope = field(default_factory=AnalysisScope)
    section_status: AnalysisSectionStatus = AnalysisSectionStatus.COMPLETE

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
    evidence: list[EvidenceReference] = field(default_factory=list)


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
    object_type: str = "relation"
    related_ids: list[str] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)
    fingerprint: str = ""


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
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    snapshot_timestamp: float | None = None
    scope: AnalysisScope = field(default_factory=AnalysisScope)
    section_status: AnalysisSectionStatus = AnalysisSectionStatus.COMPLETE


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
    issue_kind: str = "logical_conflict"
    evidence_strength: EvidenceStrength = EvidenceStrength.WEAK
    evidence: list[EvidenceReference] = field(default_factory=list)
    fingerprint: str = ""


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
    evidence_strength: EvidenceStrength = EvidenceStrength.WEAK
    evidence: list[EvidenceReference] = field(default_factory=list)
    fingerprint: str = ""


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
    evidence_strength: EvidenceStrength = EvidenceStrength.MODERATE
    evidence: list[EvidenceReference] = field(default_factory=list)
    fingerprint: str = ""


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
        snapshot_timestamp: Unix timestamp when the analyzed world snapshot
            was captured.
    """

    timestamp: float
    plot_holes: list[PlotHole]
    relation_proposals: list[RelationProposal]
    lore_suggestions: list[LoreGapFiller]
    analysis_model: str
    audit_log: list[dict[str, Any]]
    calendar_config: Any | None = None
    snapshot_timestamp: float | None = None
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    scope: AnalysisScope = field(default_factory=AnalysisScope)
    preset: AnalysisPreset = AnalysisPreset.BALANCED
    section_statuses: dict[str, AnalysisSectionStatus] = field(default_factory=dict)
    coverage: dict[str, AnalysisCoverage] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
