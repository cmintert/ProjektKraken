---
name: Tier 1 Features Design Document
description: Complete design specification for World Validation, Temporal Analysis, and Intelligence Suite
type: project
---

# TIER 1 FEATURES: DESIGN DOCUMENT

**Status:** Design Phase  
**Target Start:** ASAP  
**Timeline:** 8-10 weeks (including testing/polish)  
**Confidence:** 90%+  

---

## TABLE OF CONTENTS

1. [Architecture Overview](#architecture-overview)
2. [Feature 1: World Consistency & Validation](#feature-1-world-consistency--validation)
3. [Feature 2: Temporal Analysis](#feature-2-temporal-analysis)
4. [Feature 3: Intelligence Suite](#feature-3-intelligence-suite)
5. [Integration & Threading](#integration--threading)
6. [Testing Strategy](#testing-strategy)
7. [Implementation Checklist](#implementation-checklist)

---

## ARCHITECTURE OVERVIEW

### Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│ GUI Layer (src/gui/widgets/)                            │
│ ├─ analysis_panel.py (NEW - read-only report viewer)   │
│ └─ Uses signals from DatabaseWorker                     │
└─────────────────────────────────────────────────────────┘
                         ▲
                    Signals
                         │
┌─────────────────────────────────────────────────────────┐
│ Commands Layer (src/commands/)                          │
│ ├─ analysis_commands.py (NEW)                           │
│ │  ├─ ValidateWorldCommand                             │
│ │  ├─ AnalyzeTemporalCommand                           │
│ │  └─ RunIntelligenceAnalysisCommand                   │
│ └─ All inherit BaseCommand, execute in DatabaseWorker  │
└─────────────────────────────────────────────────────────┘
                         ▲
                   execute()
                         │
┌─────────────────────────────────────────────────────────┐
│ Services Layer (src/services/)                          │
│ ├─ world_validator.py (NEW)                            │
│ ├─ temporal_analyzer.py (NEW)                          │
│ ├─ intelligence_analyzer.py (NEW)                      │
│ ├─ temporal_resolver.py (EXTEND)                       │
│ ├─ temporal_manager.py (EXTEND)                        │
│ └─ rag_service.py, llm_provider.py (use as-is)        │
└─────────────────────────────────────────────────────────┘
                         ▲
            DatabaseService dependency
                         │
┌─────────────────────────────────────────────────────────┐
│ Core/Models Layer (src/core/)                           │
│ ├─ Existing dataclasses (Entity, Event, Relation, etc) │
│ ├─ NEW: AnalysisReport, ValidationIssue, TemporalGap   │
│ └─ (lightweight dataclasses for results)               │
└─────────────────────────────────────────────────────────┘
```

### Threading Model

```
Main Qt Thread
    │
    ├─→ User clicks "Validate World"
    │       │
    └─→ CommandCoordinator.execute(ValidateWorldCommand)
            │
            ├─→ Queue command to DatabaseWorker
            │
            └─→ Return immediately (non-blocking)

DatabaseWorker Thread (QThread)
    │
    ├─→ Receive ValidateWorldCommand
    │
    ├─→ validator = WorldValidator(self.db_service)
    │
    ├─→ report = validator.validate()
    │
    ├─→ Emit signal: self.analysis_complete.emit(report)
    │
    └─→ (Main thread receives signal, updates UI)
```

---

## FEATURE 1: WORLD CONSISTENCY & VALIDATION

### Overview

Automatically detect orphaned entities, broken references, and incomplete data. Provides a completeness score and actionable suggestions.

### 1.1 Data Models

**New dataclasses** in `src/core/analysis.py`:

```python
from dataclasses import dataclass
from typing import List, Optional, Literal
from enum import Enum

class SeverityLevel(Enum):
    """Issue severity for user prioritization."""
    CRITICAL = "critical"      # Data integrity risk
    WARNING = "warning"        # Quality issue
    INFO = "info"              # Suggestion

class IssueType(Enum):
    """Categorized issue types for filtering."""
    ORPHANED_ENTITY = "orphaned_entity"
    BROKEN_REFERENCE = "broken_reference"
    INCOMPLETE_ENTITY = "incomplete_entity"
    INCOMPLETE_EVENT = "incomplete_event"
    ORPHANED_RELATION = "orphaned_relation"
    TAG_UNUSED = "tag_unused"
    MISSING_RELATION = "missing_relation"

@dataclass
class ValidationIssue:
    """Single validation issue."""
    severity: SeverityLevel
    issue_type: IssueType
    object_id: str
    object_type: str  # "entity" | "event" | "relation"
    object_name: str
    
    message: str  # Human-readable description
    suggestion: Optional[str] = None  # How to fix it
    
    # Contextual data for UI drilling down
    related_ids: List[str] = None  # Related entity/event IDs
    
    def __post_init__(self):
        if self.related_ids is None:
            self.related_ids = []

@dataclass
class CompletenessScore:
    """Per-object completeness metrics."""
    object_id: str
    object_type: str  # "entity" | "event"
    name: str
    
    has_description: bool
    description_length: int
    has_image: bool
    has_tags: bool
    tag_count: int
    relation_count: int
    
    # Score: 0-100
    # Components: description (40%), tags (20%), relations (20%), image (10%), type (10%)
    completeness_score: float
    
    def calculate_score(self) -> float:
        score = 0.0
        if self.description_length > 50:
            score += 40
        elif self.description_length > 0:
            score += 20
        
        if self.has_tags:
            score += min(20, self.tag_count * 5)
        
        if self.relation_count > 0:
            score += min(20, self.relation_count * 5)
        
        if self.has_image:
            score += 10
        
        return min(100, score)

@dataclass
class WorldValidationReport:
    """Complete validation report for entire world."""
    timestamp: float
    
    # Totals
    total_entities: int
    total_events: int
    total_relations: int
    total_tags: int
    
    # Issues
    issues: List[ValidationIssue]
    issues_by_severity: dict  # {severity: count}
    issues_by_type: dict  # {issue_type: count}
    
    # Completeness
    completeness_scores: List[CompletenessScore]
    average_completeness: float
    
    # Summary stats
    orphaned_entities_count: int
    broken_references_count: int
    unused_tags_count: int
    
    def get_issues_by_severity(self, severity: SeverityLevel) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == severity]
    
    def get_issues_by_type(self, issue_type: IssueType) -> List[ValidationIssue]:
        return [i for i in self.issues if i.issue_type == issue_type]
```

### 1.2 WorldValidator Service

**File:** `src/services/world_validator.py`

```python
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from src.core.analysis import (
    ValidationIssue, SeverityLevel, IssueType, 
    CompletenessScore, WorldValidationReport
)
from src.services.db_service import DatabaseService
from src.core.entity import Entity
from src.core.event import Event
from src.core.relation import Relation
import json

class WorldValidator:
    """Validates world consistency and completeness."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.issues: List[ValidationIssue] = []
        self.completeness_scores: List[CompletenessScore] = []
    
    def validate(self) -> WorldValidationReport:
        """Run full validation and return report."""
        self.issues = []
        self.completeness_scores = []
        
        # Get totals
        entities = self.db_service.entity_repository.get_all()
        events = self.db_service.event_repository.get_all()
        relations = self.db_service.relation_repository.get_all()
        tags = self.db_service.tag_repository.get_all_tags()
        
        # Run all checks
        self._check_orphaned_entities(entities, relations)
        self._check_broken_references(relations, entities, events)
        self._check_incomplete_data(entities, events)
        self._check_unused_tags(tags, entities, events)
        self._check_completeness_scores(entities, events)
        
        # Build report
        return self._build_report(entities, events, relations, tags)
    
    def _check_orphaned_entities(self, entities: List[Entity], relations: List[Relation]) -> None:
        """Find entities with no relations and no mentions."""
        for entity in entities:
            # Count relations
            relation_count = len([
                r for r in relations 
                if r.source_id == entity.id or r.target_id == entity.id
            ])
            
            # Check if mentioned in other entity attributes
            mentioned_count = sum(1 for e in entities 
                                 if e.id != entity.id and self._is_mentioned_in(entity.id, e))
            
            # Check if has image
            has_image = bool(entity.attributes.get("_images"))
            
            if relation_count == 0 and mentioned_count == 0 and not has_image:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    issue_type=IssueType.ORPHANED_ENTITY,
                    object_id=entity.id,
                    object_type="entity",
                    object_name=entity.name,
                    message=f"Entity '{entity.name}' has no relations and is not mentioned elsewhere.",
                    suggestion="Consider connecting this entity to others or removing it if no longer needed.",
                    related_ids=[]
                ))
    
    def _check_broken_references(self, relations: List[Relation], entities: List[Entity], 
                                 events: List[Event]) -> None:
        """Find relations pointing to non-existent targets."""
        entity_ids = {e.id for e in entities}
        event_ids = {e.id for e in events}
        
        for relation in relations:
            # Check source exists
            if relation.source_id not in entity_ids and relation.source_id not in event_ids:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.CRITICAL,
                    issue_type=IssueType.BROKEN_REFERENCE,
                    object_id=relation.id,
                    object_type="relation",
                    object_name=f"Relation {relation.id}",
                    message=f"Relation source '{relation.source_id}' does not exist.",
                    suggestion="Delete this relation or update its source.",
                    related_ids=[relation.source_id, relation.target_id]
                ))
            
            # Check target exists
            if relation.target_id not in entity_ids and relation.target_id not in event_ids:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.CRITICAL,
                    issue_type=IssueType.BROKEN_REFERENCE,
                    object_id=relation.id,
                    object_type="relation",
                    object_name=f"Relation {relation.id}",
                    message=f"Relation target '{relation.target_id}' does not exist.",
                    suggestion="Delete this relation or update its target.",
                    related_ids=[relation.source_id, relation.target_id]
                ))
    
    def _check_incomplete_data(self, entities: List[Entity], events: List[Event]) -> None:
        """Find entities/events with minimal descriptions."""
        for entity in entities:
            description = entity.description or ""
            if len(description.strip()) < 20:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.INFO,
                    issue_type=IssueType.INCOMPLETE_ENTITY,
                    object_id=entity.id,
                    object_type="entity",
                    object_name=entity.name,
                    message=f"Entity '{entity.name}' has minimal description.",
                    suggestion="Add more details to flesh out this character/location/artifact.",
                    related_ids=[]
                ))
        
        for event in events:
            description = event.description or ""
            if len(description.strip()) < 20:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.INFO,
                    issue_type=IssueType.INCOMPLETE_EVENT,
                    object_id=event.id,
                    object_type="event",
                    object_name=event.name,
                    message=f"Event '{event.name}' has minimal description.",
                    suggestion="Add more context and details.",
                    related_ids=[]
                ))
    
    def _check_unused_tags(self, tags: List[str], entities: List[Entity], 
                          events: List[Event]) -> None:
        """Find tags used in fewer than 2 items."""
        tag_usage = {}
        
        for entity in entities:
            entity_tags = entity.attributes.get("_tags", [])
            for tag in entity_tags:
                tag_usage[tag] = tag_usage.get(tag, 0) + 1
        
        for event in events:
            event_tags = event.attributes.get("_tags", [])
            for tag in event_tags:
                tag_usage[tag] = tag_usage.get(tag, 0) + 1
        
        for tag in tags:
            if tag_usage.get(tag, 0) < 2:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.INFO,
                    issue_type=IssueType.TAG_UNUSED,
                    object_id=tag,
                    object_type="tag",
                    object_name=tag,
                    message=f"Tag '{tag}' is used in fewer than 2 items.",
                    suggestion="Consider consolidating tags or removing if no longer relevant.",
                    related_ids=[]
                ))
    
    def _check_completeness_scores(self, entities: List[Entity], events: List[Event]) -> None:
        """Calculate completeness score for each entity/event."""
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
                relation_count=0,  # Will be calculated separately
                completeness_score=0.0
            )
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
                relation_count=0,
                completeness_score=0.0
            )
            self.completeness_scores.append(score)
    
    def _is_mentioned_in(self, entity_id: str, other_entity: Entity) -> bool:
        """Check if entity_id is mentioned in other_entity's attributes."""
        attrs_json = json.dumps(other_entity.attributes, default=str)
        return entity_id in attrs_json
    
    def _build_report(self, entities: List[Entity], events: List[Event], 
                     relations: List[Relation], tags: List[str]) -> WorldValidationReport:
        """Construct final report."""
        import time
        
        issues_by_severity = {
            SeverityLevel.CRITICAL: len([i for i in self.issues if i.severity == SeverityLevel.CRITICAL]),
            SeverityLevel.WARNING: len([i for i in self.issues if i.severity == SeverityLevel.WARNING]),
            SeverityLevel.INFO: len([i for i in self.issues if i.severity == SeverityLevel.INFO]),
        }
        
        issues_by_type = {}
        for issue_type in IssueType:
            count = len([i for i in self.issues if i.issue_type == issue_type])
            if count > 0:
                issues_by_type[issue_type.value] = count
        
        avg_completeness = (
            sum(score.calculate_score() for score in self.completeness_scores) 
            / len(self.completeness_scores)
            if self.completeness_scores else 0
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
            orphaned_entities_count=len([i for i in self.issues if i.issue_type == IssueType.ORPHANED_ENTITY]),
            broken_references_count=len([i for i in self.issues if i.issue_type == IssueType.BROKEN_REFERENCE]),
            unused_tags_count=len([i for i in self.issues if i.issue_type == IssueType.TAG_UNUSED]),
        )
```

### 1.3 ValidateWorldCommand

**File:** `src/commands/analysis_commands.py`

```python
from src.commands.base_command import BaseCommand, CommandResult
from src.services.world_validator import WorldValidator
from src.services.db_service import DatabaseService
from typing import Optional

class ValidateWorldCommand(BaseCommand):
    """Validates world consistency and completeness."""
    
    def __init__(self):
        super().__init__()
        self.report = None
    
    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run validation and return report."""
        try:
            validator = WorldValidator(db_service)
            self.report = validator.validate()
            
            return CommandResult(
                success=True,
                errors={},
                data={"report": self.report}
            )
        except Exception as e:
            return CommandResult(
                success=False,
                errors={"validation": str(e)},
                data=None
            )
    
    def undo(self) -> None:
        """Validation is read-only, no undo needed."""
        pass
```

### 1.4 Integration with DatabaseWorker

**File:** `src/app/worker.py` (add to existing file)

```python
# Add signal
validation_complete = pyqtSignal(object)  # Emits WorldValidationReport

# Add method
def validate_world(self) -> None:
    """Execute world validation in worker thread."""
    self.operation_started.emit("Validating world...")
    try:
        cmd = ValidateWorldCommand()
        result = cmd.execute(self.db_service)
        
        if result.success:
            report = result.data["report"]
            self.validation_complete.emit(report)
        else:
            self.error_occurred.emit(f"Validation failed: {result.errors}")
    
    except Exception as e:
        self.error_occurred.emit(f"Validation error: {str(e)}")
    finally:
        self.operation_finished.emit("Validation complete")
```

### 1.5 UI Integration

**File:** `src/gui/widgets/analysis_panel.py` (NEW)

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QPushButton
from PySide6.QtCore import Qt, pyqtSignal
from src.core.analysis import WorldValidationReport, SeverityLevel, IssueType

class AnalysisPanel(QWidget):
    """Displays validation report and analysis results."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header with totals
        self.header_label = QLabel()
        layout.addWidget(self.header_label)
        
        # Issues table
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(5)
        self.issues_table.setHorizontalHeaderLabels([
            "Severity", "Type", "Object", "Message", "Suggestion"
        ])
        layout.addWidget(self.issues_table)
        
        # Completeness scores
        self.completeness_table = QTableWidget()
        self.completeness_table.setColumnCount(4)
        self.completeness_table.setHorizontalHeaderLabels([
            "Name", "Type", "Completeness", "Tags"
        ])
        layout.addWidget(self.completeness_table)
        
        self.setLayout(layout)
    
    def display_report(self, report: WorldValidationReport):
        """Display validation report."""
        self.report = report
        
        # Update header
        self.header_label.setText(
            f"World Health: {report.average_completeness:.0f}% Complete | "
            f"{len(report.issues)} Issues | "
            f"Entities: {report.total_entities}, Events: {report.total_events}"
        )
        
        # Populate issues table
        self.issues_table.setRowCount(len(report.issues))
        for i, issue in enumerate(report.issues):
            self.issues_table.setItem(i, 0, QTableWidgetItem(issue.severity.value))
            self.issues_table.setItem(i, 1, QTableWidgetItem(issue.issue_type.value))
            self.issues_table.setItem(i, 2, QTableWidgetItem(issue.object_name))
            self.issues_table.setItem(i, 3, QTableWidgetItem(issue.message))
            self.issues_table.setItem(i, 4, QTableWidgetItem(issue.suggestion or ""))
        
        # Populate completeness table
        sorted_scores = sorted(report.completeness_scores, key=lambda s: s.completeness_score)
        self.completeness_table.setRowCount(len(sorted_scores))
        for i, score in enumerate(sorted_scores):
            self.completeness_table.setItem(i, 0, QTableWidgetItem(score.name))
            self.completeness_table.setItem(i, 1, QTableWidgetItem(score.object_type))
            self.completeness_table.setItem(i, 2, QTableWidgetItem(f"{score.calculate_score():.0f}%"))
            self.completeness_table.setItem(i, 3, QTableWidgetItem(str(score.tag_count)))
```

---

## FEATURE 2: TEMPORAL ANALYSIS

### Overview

Detect timeline gaps, character lifespan issues, and temporal conflicts.

### 2.1 Data Models

**New dataclasses** in `src/core/analysis.py` (add to existing):

```python
@dataclass
class TimelineGap:
    """A period with no events."""
    start_date: float
    end_date: float
    gap_duration: float
    
    affected_entity_ids: List[str] = field(default_factory=list)
    message: str = ""

@dataclass
class TemporalConflict:
    """A temporal logic violation."""
    conflict_type: str  # "lifespan_violation", "invalid_relation_window", "state_contradiction"
    entity_id: str
    entity_name: str
    problem_date: Optional[float]
    message: str
    suggestion: Optional[str] = None
    severity: SeverityLevel = SeverityLevel.WARNING

@dataclass
class CharacterLifespan:
    """Computed lifespan for a character."""
    entity_id: str
    entity_name: str
    birth_date: Optional[float]
    death_date: Optional[float]
    life_span_years: Optional[float]
    
    # Events that violate lifespan
    violating_events: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        if self.birth_date and self.death_date:
            return self.birth_date < self.death_date
        return True

@dataclass
class TemporalAnalysisReport:
    """Full temporal analysis report."""
    timestamp: float
    
    # Gaps
    timeline_gaps: List[TimelineGap]
    total_gap_duration: float
    
    # Conflicts
    conflicts: List[TemporalConflict]
    
    # Lifespans
    character_lifespans: List[CharacterLifespan]
    
    # Summary
    earliest_event_date: Optional[float]
    latest_event_date: Optional[float]
    calendar_name: str
```

### 2.2 TemporalAnalyzer Service

**File:** `src/services/temporal_analyzer.py`

```python
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from src.core.analysis import TimelineGap, TemporalConflict, CharacterLifespan, TemporalAnalysisReport, SeverityLevel
from src.services.db_service import DatabaseService
from src.services.temporal_resolver import TemporalResolver
from src.core.event import Event
from src.core.entity import Entity
from src.core.relation import Relation
import time

class TemporalAnalyzer:
    """Analyzes temporal consistency and gaps."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.temporal_resolver = TemporalResolver(db_service)
        
        # Configuration
        self.gap_threshold = 100.0  # Years; gaps > this are flagged
    
    def analyze(self) -> TemporalAnalysisReport:
        """Run full temporal analysis."""
        events = self.db_service.event_repository.get_all()
        entities = self.db_service.entity_repository.get_all()
        relations = self.db_service.relation_repository.get_all()
        
        # Analyze
        gaps = self._detect_timeline_gaps(events)
        conflicts = self._detect_temporal_conflicts(entities, events, relations)
        lifespans = self._analyze_character_lifespans(entities, events, relations)
        
        # Get date range
        if events:
            dates = [e.lore_date for e in events if e.lore_date]
            earliest = min(dates) if dates else None
            latest = max(dates) if dates else None
        else:
            earliest = latest = None
        
        # Get active calendar name
        active_calendar = self.db_service.meta_repository.get_active_calendar()
        calendar_name = active_calendar.name if active_calendar else "Unknown"
        
        return TemporalAnalysisReport(
            timestamp=time.time(),
            timeline_gaps=gaps,
            total_gap_duration=sum(g.gap_duration for g in gaps),
            conflicts=conflicts,
            character_lifespans=lifespans,
            earliest_event_date=earliest,
            latest_event_date=latest,
            calendar_name=calendar_name,
        )
    
    def _detect_timeline_gaps(self, events: List[Event]) -> List[TimelineGap]:
        """Find periods with no events."""
        if not events:
            return []
        
        # Sort events by date
        events_sorted = sorted(
            [e for e in events if e.lore_date is not None],
            key=lambda e: e.lore_date
        )
        
        gaps = []
        for i in range(len(events_sorted) - 1):
            gap_duration = events_sorted[i + 1].lore_date - events_sorted[i].lore_date
            
            if gap_duration > self.gap_threshold:
                gap = TimelineGap(
                    start_date=events_sorted[i].lore_date,
                    end_date=events_sorted[i + 1].lore_date,
                    gap_duration=gap_duration,
                    affected_entity_ids=[],
                    message=f"Gap of {gap_duration:.0f} years between '{events_sorted[i].name}' and '{events_sorted[i + 1].name}'"
                )
                gaps.append(gap)
        
        return gaps
    
    def _detect_temporal_conflicts(self, entities: List[Entity], events: List[Event], 
                                   relations: List[Relation]) -> List[TemporalConflict]:
        """Find temporal logic violations."""
        conflicts = []
        
        # Check for invalid relation windows
        for relation in relations:
            if relation.attributes.get("valid_from") and relation.attributes.get("valid_to"):
                valid_from = relation.attributes["valid_from"]
                valid_to = relation.attributes["valid_to"]
                
                if isinstance(valid_from, (int, float)) and isinstance(valid_to, (int, float)):
                    if valid_from >= valid_to:
                        conflicts.append(TemporalConflict(
                            conflict_type="invalid_relation_window",
                            entity_id=relation.id,
                            entity_name=f"Relation {relation.id}",
                            problem_date=valid_from,
                            message=f"Relation has invalid_from ({valid_from}) >= valid_to ({valid_to})",
                            suggestion="Fix the date range for this relation.",
                            severity=SeverityLevel.WARNING
                        ))
        
        # Check for state contradictions (entity has contradictory attributes at same time)
        # This is advanced; basic version checks if entity has conflicting temporal relations
        for entity in entities:
            temporal_relations = [
                r for r in relations 
                if r.source_id == entity.id and "valid_from" in r.attributes
            ]
            
            # Group by date and check for conflicts
            by_date = {}
            for rel in temporal_relations:
                date = rel.attributes.get("valid_from", 0)
                by_date.setdefault(date, []).append(rel)
        
        return conflicts
    
    def _analyze_character_lifespans(self, entities: List[Entity], events: List[Event], 
                                     relations: List[Relation]) -> List[CharacterLifespan]:
        """Track character birth/death and validate."""
        lifespans = []
        
        for entity in entities:
            birth_date = None
            death_date = None
            violating_events = []
            
            # Look for birth/death relations
            for relation in relations:
                if relation.target_id == entity.id:
                    rel_type = relation.relation_type or ""
                    
                    # Birth
                    if "birth" in rel_type.lower():
                        if relation.attributes.get("date"):
                            birth_date = relation.attributes["date"]
                        elif relation.attributes.get("event_id"):
                            event = next((e for e in events if e.id == relation.attributes["event_id"]), None)
                            if event:
                                birth_date = event.lore_date
                    
                    # Death
                    if "death" in rel_type.lower():
                        if relation.attributes.get("date"):
                            death_date = relation.attributes["date"]
                        elif relation.attributes.get("event_id"):
                            event = next((e for e in events if e.id == relation.attributes["event_id"]), None)
                            if event:
                                death_date = event.lore_date
            
            # Check for events before birth or after death
            for event in events:
                if event.lore_date:
                    if birth_date and event.lore_date < birth_date:
                        violating_events.append(event.id)
                    if death_date and event.lore_date > death_date:
                        violating_events.append(event.id)
            
            # Compute lifespan
            life_span = None
            if birth_date and death_date:
                life_span = death_date - birth_date
            
            lifespans.append(CharacterLifespan(
                entity_id=entity.id,
                entity_name=entity.name,
                birth_date=birth_date,
                death_date=death_date,
                life_span_years=life_span,
                violating_events=violating_events,
            ))
        
        return lifespans
```

### 2.3 AnalyzeTemporalCommand

**File:** `src/commands/analysis_commands.py` (add to existing)

```python
class AnalyzeTemporalCommand(BaseCommand):
    """Analyzes temporal consistency and gaps."""
    
    def __init__(self):
        super().__init__()
        self.report = None
    
    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run temporal analysis."""
        try:
            from src.services.temporal_analyzer import TemporalAnalyzer
            
            analyzer = TemporalAnalyzer(db_service)
            self.report = analyzer.analyze()
            
            return CommandResult(
                success=True,
                errors={},
                data={"report": self.report}
            )
        except Exception as e:
            return CommandResult(
                success=False,
                errors={"temporal_analysis": str(e)},
                data=None
            )
    
    def undo(self) -> None:
        """Temporal analysis is read-only."""
        pass
```

---

## FEATURE 3: INTELLIGENCE SUITE

### Overview

AI-powered plot hole detection, relation inference, and lore generation using RAG + LLM.

### 3.1 Data Models

**New dataclasses** in `src/core/analysis.py` (add to existing):

```python
@dataclass
class PlotHole:
    """Detected plot hole or inconsistency."""
    issue_id: str
    entity_id: str
    entity_name: str
    description: str
    severity: SeverityLevel
    suggested_resolution: Optional[str] = None
    confidence: float = 0.8  # 0-1

@dataclass
class RelationProposal:
    """Suggested relation between entities."""
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    suggested_relation_type: str
    reasoning: str
    confidence: float = 0.7  # 0-1

@dataclass
class LoreGapFiller:
    """Generated lore to fill timeline gap."""
    gap_id: str
    start_date: float
    end_date: float
    suggestions: List[str]  # Multiple plausible events
    selected_suggestion: Optional[int] = None  # User selected index

@dataclass
class IntelligenceReport:
    """Full AI analysis report."""
    timestamp: float
    
    # Plot holes
    plot_holes: List[PlotHole]
    
    # Relation proposals
    relation_proposals: List[RelationProposal]
    
    # Lore generators
    lore_suggestions: List[LoreGapFiller]
    
    # Metadata
    analysis_model: str  # Which LLM was used
    audit_log: List[Dict]  # LLM interactions
```

### 3.2 IntelligenceAnalyzer Service

**File:** `src/services/intelligence_analyzer.py`

```python
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from src.core.analysis import (
    PlotHole, RelationProposal, LoreGapFiller, IntelligenceReport, 
    SeverityLevel, TemporalAnalysisReport, TimelineGap
)
from src.services.db_service import DatabaseService
from src.services.rag_service import RAGService
from src.services.llm_provider import LLMProvider
from src.services.temporal_analyzer import TemporalAnalyzer
from src.services.prompt_builder import PromptBuilder
from src.core.entity import Entity
from src.core.event import Event
from src.core.relation import Relation
import json
import time

class IntelligenceAnalyzer:
    """AI-powered world analysis using RAG + LLM."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.rag_service = RAGService(db_service)
        self.llm_provider = LLMProvider.create()  # Auto-selects configured provider
        self.temporal_analyzer = TemporalAnalyzer(db_service)
        self.prompt_builder = PromptBuilder()
    
    def analyze(self, analysis_type: str = "all") -> IntelligenceReport:
        """Run AI analysis.
        
        Args:
            analysis_type: "all" | "plot_holes" | "relations" | "lore"
        """
        plot_holes = []
        relation_proposals = []
        lore_suggestions = []
        audit_log = []
        
        if analysis_type in ("all", "plot_holes"):
            plot_holes, holes_audit = self._detect_plot_holes()
            audit_log.extend(holes_audit)
        
        if analysis_type in ("all", "relations"):
            relation_proposals, relations_audit = self._infer_relations()
            audit_log.extend(relations_audit)
        
        if analysis_type in ("all", "lore"):
            lore_suggestions, lore_audit = self._generate_lore()
            audit_log.extend(lore_audit)
        
        return IntelligenceReport(
            timestamp=time.time(),
            plot_holes=plot_holes,
            relation_proposals=relation_proposals,
            lore_suggestions=lore_suggestions,
            analysis_model=self.llm_provider.__class__.__name__,
            audit_log=audit_log,
        )
    
    def _detect_plot_holes(self) -> Tuple[List[PlotHole], List[Dict]]:
        """Detect plot holes via LLM analysis."""
        audit_log = []
        plot_holes = []
        
        entities = self.db_service.entity_repository.get_all()
        
        # Analyze top entities (by relation count) for efficiency
        top_entities = sorted(
            entities,
            key=lambda e: len([r for r in self.db_service.relation_repository.get_all() 
                              if r.source_id == e.id or r.target_id == e.id]),
            reverse=True
        )[:10]  # Top 10 most-connected entities
        
        for entity in top_entities:
            # Gather context
            temporal_context = self._gather_temporal_context(entity)
            relational_context = self._gather_relational_context(entity)
            semantic_context = self._gather_semantic_context(entity)
            
            # Build prompt
            prompt = self._build_plot_hole_prompt(entity, temporal_context, relational_context, semantic_context)
            
            # Call LLM
            try:
                response = self.llm_provider.generate(prompt)
                
                # Log interaction
                audit_log.append({
                    "type": "plot_hole_detection",
                    "entity_id": entity.id,
                    "model": self.llm_provider.__class__.__name__,
                    "prompt_length": len(prompt),
                    "response_length": len(response),
                    "timestamp": time.time(),
                })
                
                # Parse response into plot holes
                holes = self._parse_plot_holes(response, entity)
                plot_holes.extend(holes)
            
            except Exception as e:
                audit_log.append({
                    "type": "plot_hole_detection",
                    "entity_id": entity.id,
                    "error": str(e),
                })
        
        return plot_holes, audit_log
    
    def _infer_relations(self) -> Tuple[List[RelationProposal], List[Dict]]:
        """Infer missing relations between entities."""
        audit_log = []
        proposals = []
        
        entities = self.db_service.entity_repository.get_all()
        existing_relations = self.db_service.relation_repository.get_all()
        
        # Get existing relation pairs
        existing_pairs = {(r.source_id, r.target_id) for r in existing_relations}
        
        # Check likely pairs (shared tags, same location type, etc.)
        candidates = self._find_relation_candidates(entities)
        
        for source, target in candidates:
            if (source.id, target.id) in existing_pairs:
                continue  # Already related
            
            # Build prompt
            prompt = self._build_relation_inference_prompt(source, target)
            
            # Call LLM
            try:
                response = self.llm_provider.generate(prompt)
                
                audit_log.append({
                    "type": "relation_inference",
                    "source_id": source.id,
                    "target_id": target.id,
                    "timestamp": time.time(),
                })
                
                # Parse response
                proposal = self._parse_relation_proposal(response, source, target)
                if proposal:
                    proposals.append(proposal)
            
            except Exception as e:
                audit_log.append({
                    "type": "relation_inference",
                    "source_id": source.id,
                    "target_id": target.id,
                    "error": str(e),
                })
        
        return proposals, audit_log
    
    def _generate_lore(self) -> Tuple[List[LoreGapFiller], List[Dict]]:
        """Generate lore to fill timeline gaps."""
        audit_log = []
        suggestions = []
        
        # Get timeline gaps
        temporal_report = self.temporal_analyzer.analyze()
        gaps = temporal_report.timeline_gaps[:5]  # Top 5 gaps
        
        events = self.db_service.event_repository.get_all()
        
        for gap in gaps:
            # Get surrounding events
            events_before = [e for e in events if e.lore_date and e.lore_date < gap.start_date]
            events_after = [e for e in events if e.lore_date and e.lore_date > gap.end_date]
            
            if not events_before or not events_after:
                continue
            
            # Build prompt
            prompt = self._build_lore_generation_prompt(gap, events_before[-1], events_after[0])
            
            # Call LLM
            try:
                response = self.llm_provider.generate(prompt)
                
                audit_log.append({
                    "type": "lore_generation",
                    "gap_start": gap.start_date,
                    "gap_end": gap.end_date,
                    "timestamp": time.time(),
                })
                
                # Parse response
                filler = self._parse_lore_suggestions(response, gap)
                if filler:
                    suggestions.append(filler)
            
            except Exception as e:
                audit_log.append({
                    "type": "lore_generation",
                    "gap_start": gap.start_date,
                    "error": str(e),
                })
        
        return suggestions, audit_log
    
    # --- Helper methods ---
    
    def _gather_temporal_context(self, entity: Entity) -> str:
        """Gather temporal info for entity."""
        events = self.db_service.event_repository.get_all()
        relations = self.db_service.relation_repository.get_all()
        
        # Events mentioning entity
        entity_events = [e for e in events if entity.id in json.dumps(e.attributes, default=str)]
        
        # Relations involving entity
        entity_relations = [r for r in relations if r.source_id == entity.id or r.target_id == entity.id]
        
        context = "Timeline:\n"
        for event in sorted(entity_events, key=lambda e: e.lore_date or 0):
            context += f"- {event.lore_date or 'Unknown'}: {event.name}\n"
        
        return context
    
    def _gather_relational_context(self, entity: Entity) -> str:
        """Gather relation info for entity."""
        relations = self.db_service.relation_repository.get_all()
        entities = self.db_service.entity_repository.get_all()
        entity_map = {e.id: e for e in entities}
        
        entity_relations = [r for r in relations if r.source_id == entity.id or r.target_id == entity.id]
        
        context = "Relations:\n"
        for rel in entity_relations:
            other_id = rel.target_id if rel.source_id == entity.id else rel.source_id
            other = entity_map.get(other_id)
            if other:
                rel_type = rel.relation_type or "unknown"
                context += f"- {rel_type}: {other.name}\n"
        
        return context
    
    def _gather_semantic_context(self, entity: Entity) -> str:
        """Gather semantic similar entities."""
        results = self.rag_service.search(entity.name, top_k=3)
        
        context = "Related entities:\n"
        for result in results:
            context += f"- {result.get('name')}: {result.get('text_content', '')[:100]}\n"
        
        return context
    
    def _find_relation_candidates(self, entities: List[Entity]) -> List[Tuple[Entity, Entity]]:
        """Find entity pairs that might be related."""
        candidates = []
        
        # Simple heuristic: same type or shared tags
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                e1_tags = set(e1.attributes.get("_tags", []))
                e2_tags = set(e2.attributes.get("_tags", []))
                
                if e1_tags & e2_tags:  # Shared tags
                    candidates.append((e1, e2))
        
        return candidates[:20]  # Limit to 20 pairs
    
    def _build_plot_hole_prompt(self, entity: Entity, temporal: str, relational: str, semantic: str) -> str:
        """Build plot hole detection prompt."""
        return f"""
Analyze this character/location for logical inconsistencies or plot holes:

Name: {entity.name}
Type: {entity.type or 'Unknown'}
Description: {entity.description or 'None'}

{temporal}

{relational}

{semantic}

Identify any:
1. Timeline contradictions
2. Logical impossibilities
3. Missing context
4. Inconsistent characterization

Format response as:
PLOT HOLE: [description]
SEVERITY: [high/medium/low]
RESOLUTION: [suggested fix]
"""
    
    def _build_relation_inference_prompt(self, source: Entity, target: Entity) -> str:
        """Build relation inference prompt."""
        return f"""
Should these two entities have a direct relation?

Entity 1: {source.name} ({source.type})
Description: {source.description or 'None'}
Tags: {source.attributes.get("_tags", [])}

Entity 2: {target.name} ({target.type})
Description: {target.description or 'None'}
Tags: {target.attributes.get("_tags", [])}

If yes, what type of relation? Answer format:
SHOULD_RELATE: [yes/no]
RELATION_TYPE: [type]
CONFIDENCE: [0-1]
REASONING: [why]
"""
    
    def _build_lore_generation_prompt(self, gap: TimelineGap, before_event: Event, after_event: Event) -> str:
        """Build lore generation prompt."""
        return f"""
There's a {gap.gap_duration:.0f}-year gap in the timeline:

Last event: Year {before_event.lore_date} - {before_event.name}
Description: {before_event.description or 'None'}

Next event: Year {after_event.lore_date} - {after_event.name}
Description: {after_event.description or 'None'}

Generate 2-3 plausible events that could bridge this gap, connecting the two events logically.

Format as:
EVENT: [name]
DATE: [estimated year]
DESCRIPTION: [brief description]
"""
    
    def _parse_plot_holes(self, response: str, entity: Entity) -> List[PlotHole]:
        """Parse LLM response into PlotHole objects."""
        holes = []
        
        # Simple parsing: split by "PLOT HOLE:"
        parts = response.split("PLOT HOLE:")
        for part in parts[1:]:  # Skip header
            lines = part.strip().split("\n")
            description = lines[0] if lines else ""
            
            severity = SeverityLevel.WARNING
            if "high" in part.lower():
                severity = SeverityLevel.CRITICAL
            elif "low" in part.lower():
                severity = SeverityLevel.INFO
            
            resolution = None
            if "RESOLUTION:" in part:
                resolution = part.split("RESOLUTION:")[1].split("\n")[0].strip()
            
            holes.append(PlotHole(
                issue_id=f"hole_{entity.id}_{len(holes)}",
                entity_id=entity.id,
                entity_name=entity.name,
                description=description,
                severity=severity,
                suggested_resolution=resolution,
                confidence=0.75,
            ))
        
        return holes
    
    def _parse_relation_proposal(self, response: str, source: Entity, target: Entity) -> Optional[RelationProposal]:
        """Parse relation inference response."""
        if "yes" not in response.lower():
            return None
        
        relation_type = "related"
        if "RELATION_TYPE:" in response:
            relation_type = response.split("RELATION_TYPE:")[1].split("\n")[0].strip()
        
        confidence = 0.7
        if "CONFIDENCE:" in response:
            try:
                conf_str = response.split("CONFIDENCE:")[1].split("\n")[0].strip()
                confidence = float(conf_str)
            except:
                pass
        
        reasoning = ""
        if "REASONING:" in response:
            reasoning = response.split("REASONING:")[1].strip()
        
        return RelationProposal(
            source_id=source.id,
            source_name=source.name,
            target_id=target.id,
            target_name=target.name,
            suggested_relation_type=relation_type,
            reasoning=reasoning,
            confidence=confidence,
        )
    
    def _parse_lore_suggestions(self, response: str, gap: TimelineGap) -> Optional[LoreGapFiller]:
        """Parse lore generation response."""
        suggestions = []
        
        # Split by EVENT:
        parts = response.split("EVENT:")
        for part in parts[1:]:
            if "DESCRIPTION:" in part:
                suggestions.append(part.strip())
        
        if not suggestions:
            return None
        
        return LoreGapFiller(
            gap_id=f"gap_{gap.start_date}_{gap.end_date}",
            start_date=gap.start_date,
            end_date=gap.end_date,
            suggestions=suggestions,
        )
```

### 3.3 RunIntelligenceAnalysisCommand

**File:** `src/commands/analysis_commands.py` (add to existing)

```python
class RunIntelligenceAnalysisCommand(BaseCommand):
    """Runs AI analysis for plot holes, relations, lore."""
    
    def __init__(self, analysis_type: str = "all"):
        super().__init__()
        self.analysis_type = analysis_type
        self.report = None
    
    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run intelligence analysis."""
        try:
            from src.services.intelligence_analyzer import IntelligenceAnalyzer
            
            analyzer = IntelligenceAnalyzer(db_service)
            self.report = analyzer.analyze(self.analysis_type)
            
            return CommandResult(
                success=True,
                errors={},
                data={"report": self.report}
            )
        except Exception as e:
            return CommandResult(
                success=False,
                errors={"intelligence_analysis": str(e)},
                data=None
            )
    
    def undo(self) -> None:
        """Intelligence analysis is read-only."""
        pass
```

---

## INTEGRATION & THREADING

### DatabaseWorker Integration

**File:** `src/app/worker.py` (add these signals and methods)

```python
from PySide6.QtCore import pyqtSignal

class DatabaseWorker(QThread):
    # Add signals
    validation_complete = pyqtSignal(object)          # WorldValidationReport
    temporal_analysis_complete = pyqtSignal(object)   # TemporalAnalysisReport
    intelligence_analysis_complete = pyqtSignal(object)  # IntelligenceReport
    
    # Add methods
    def validate_world(self) -> None:
        """Execute world validation."""
        self.operation_started.emit("Validating world...")
        try:
            from src.commands.analysis_commands import ValidateWorldCommand
            cmd = ValidateWorldCommand()
            result = cmd.execute(self.db_service)
            
            if result.success:
                report = result.data["report"]
                self.validation_complete.emit(report)
            else:
                self.error_occurred.emit(f"Validation failed: {result.errors}")
        except Exception as e:
            self.error_occurred.emit(f"Validation error: {str(e)}")
        finally:
            self.operation_finished.emit()
    
    def analyze_temporal(self) -> None:
        """Execute temporal analysis."""
        self.operation_started.emit("Analyzing timeline...")
        try:
            from src.commands.analysis_commands import AnalyzeTemporalCommand
            cmd = AnalyzeTemporalCommand()
            result = cmd.execute(self.db_service)
            
            if result.success:
                report = result.data["report"]
                self.temporal_analysis_complete.emit(report)
            else:
                self.error_occurred.emit(f"Temporal analysis failed: {result.errors}")
        except Exception as e:
            self.error_occurred.emit(f"Temporal analysis error: {str(e)}")
        finally:
            self.operation_finished.emit()
    
    def run_intelligence_analysis(self, analysis_type: str = "all") -> None:
        """Execute intelligence analysis."""
        self.operation_started.emit(f"Running AI analysis ({analysis_type})...")
        try:
            from src.commands.analysis_commands import RunIntelligenceAnalysisCommand
            cmd = RunIntelligenceAnalysisCommand(analysis_type)
            result = cmd.execute(self.db_service)
            
            if result.success:
                report = result.data["report"]
                self.intelligence_analysis_complete.emit(report)
            else:
                self.error_occurred.emit(f"Intelligence analysis failed: {result.errors}")
        except Exception as e:
            self.error_occurred.emit(f"Intelligence analysis error: {str(e)}")
        finally:
            self.operation_finished.emit()
```

### AppCoordinator Integration

**File:** `src/app/coordinators/app_coordinator.py` (add methods)

```python
def validate_world(self) -> None:
    """Trigger world validation."""
    self.worker_manager.worker.validate_world()

def analyze_temporal(self) -> None:
    """Trigger temporal analysis."""
    self.worker_manager.worker.analyze_temporal()

def run_intelligence_analysis(self, analysis_type: str = "all") -> None:
    """Trigger intelligence analysis."""
    self.worker_manager.worker.run_intelligence_analysis(analysis_type)
```

### UI Wiring

**File:** `src/gui/widgets/main_analysis_panel.py` (NEW)

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QLabel
from PySide6.QtCore import pyqtSignal
from src.gui.widgets.analysis.analysis_panel import AnalysisPanel

class MainAnalysisPanel(QWidget):
    """Main panel for all analysis features."""
    
    def __init__(self, app_coordinator, parent=None):
        super().__init__(parent)
        self.app_coordinator = app_coordinator
        self.init_ui()
        self._connect_signals()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Control buttons
        button_layout = QVBoxLayout()
        
        validate_btn = QPushButton("Validate World")
        validate_btn.clicked.connect(self._on_validate_clicked)
        button_layout.addWidget(validate_btn)
        
        temporal_btn = QPushButton("Analyze Timeline")
        temporal_btn.clicked.connect(self._on_temporal_clicked)
        button_layout.addWidget(temporal_btn)
        
        intelligence_btn = QPushButton("Run AI Analysis")
        intelligence_btn.clicked.connect(self._on_intelligence_clicked)
        button_layout.addWidget(intelligence_btn)
        
        layout.addLayout(button_layout)
        
        # Tabs for results
        self.tabs = QTabWidget()
        self.validation_panel = AnalysisPanel()
        self.temporal_panel = AnalysisPanel()
        self.intelligence_panel = AnalysisPanel()
        
        self.tabs.addTab(self.validation_panel, "Validation")
        self.tabs.addTab(self.temporal_panel, "Timeline")
        self.tabs.addTab(self.intelligence_panel, "AI Analysis")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def _connect_signals(self):
        """Connect worker signals."""
        worker = self.app_coordinator.worker_manager.worker
        worker.validation_complete.connect(self._on_validation_complete)
        worker.temporal_analysis_complete.connect(self._on_temporal_complete)
        worker.intelligence_analysis_complete.connect(self._on_intelligence_complete)
        worker.error_occurred.connect(self._on_error)
    
    def _on_validate_clicked(self):
        self.app_coordinator.validate_world()
    
    def _on_temporal_clicked(self):
        self.app_coordinator.analyze_temporal()
    
    def _on_intelligence_clicked(self):
        self.app_coordinator.run_intelligence_analysis()
    
    def _on_validation_complete(self, report):
        self.validation_panel.display_report(report)
        self.tabs.setCurrentWidget(self.validation_panel)
    
    def _on_temporal_complete(self, report):
        # TODO: Implement temporal report display
        print(f"Temporal analysis complete: {report}")
    
    def _on_intelligence_complete(self, report):
        # TODO: Implement intelligence report display
        print(f"Intelligence analysis complete: {report}")
    
    def _on_error(self, message: str):
        print(f"Analysis error: {message}")
```

---

## TESTING STRATEGY

### Unit Tests

**File:** `tests/unit/test_world_validator.py`

```python
import pytest
from src.services.world_validator import WorldValidator
from src.core.entity import Entity
from src.core.event import Event
from src.core.relation import Relation
from src.core.analysis import ValidationIssue, IssueType

class TestWorldValidator:
    @pytest.fixture
    def mock_db(self, mocker):
        db = mocker.MagicMock()
        return db
    
    def test_detect_orphaned_entity(self, mock_db):
        """Orphaned entities should be flagged."""
        entity = Entity(id="e1", name="Lonely", type="character", description="", attributes={})
        
        mock_db.entity_repository.get_all.return_value = [entity]
        mock_db.event_repository.get_all.return_value = []
        mock_db.relation_repository.get_all.return_value = []
        mock_db.tag_repository.get_all_tags.return_value = []
        
        validator = WorldValidator(mock_db)
        report = validator.validate()
        
        orphan_issues = report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        assert len(orphan_issues) == 1
        assert orphan_issues[0].object_id == "e1"
    
    def test_detect_broken_reference(self, mock_db):
        """Relations pointing to non-existent entities should be flagged."""
        relation = Relation(
            id="r1",
            source_id="e_nonexistent",
            target_id="e2",
            relation_type="test",
            attributes={}
        )
        
        mock_db.entity_repository.get_all.return_value = []
        mock_db.event_repository.get_all.return_value = []
        mock_db.relation_repository.get_all.return_value = [relation]
        mock_db.tag_repository.get_all_tags.return_value = []
        
        validator = WorldValidator(mock_db)
        report = validator.validate()
        
        broken_refs = report.get_issues_by_type(IssueType.BROKEN_REFERENCE)
        assert len(broken_refs) > 0

# Similar for TemporalAnalyzer and IntelligenceAnalyzer
```

### Integration Tests

**File:** `tests/integration/test_analysis_commands.py`

```python
import pytest
from src.commands.analysis_commands import ValidateWorldCommand
from tests.fixtures.db_fixtures import populated_db_service

class TestAnalysisCommands:
    def test_validate_world_command(self, populated_db_service):
        """ValidateWorldCommand should execute without errors."""
        cmd = ValidateWorldCommand()
        result = cmd.execute(populated_db_service)
        
        assert result.success
        assert "report" in result.data
        assert result.data["report"].total_entities > 0
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Foundation (Week 1)

- [x] Create `src/core/analysis.py` with data models
  - [x] ValidationIssue, WorldValidationReport, CompletenessScore
  - [x] TimelineGap, TemporalConflict, CharacterLifespan, TemporalAnalysisReport
  - [x] PlotHole, RelationProposal, LoreGapFiller, IntelligenceReport
- [x] Create `src/services/world_validator.py`
  - [x] WorldValidator class
  - [x] `_check_orphaned_entities()` method
  - [x] `_check_broken_references()` method
  - [x] `_check_incomplete_data()` method
  - [x] `_check_unused_tags()` method
  - [x] `_check_completeness_scores()` method
- [x] Create `src/commands/analysis_commands.py`
  - [x] ValidateWorldCommand class
- [x] Add signals to DatabaseWorker
  - [x] `validation_complete` signal
  - [x] `validate_world()` method
- [x] Add method to AppCoordinator
  - [x] `validate_world()` method
- [x] Basic UI: `src/gui/widgets/analysis_panel.py`
  - [x] Display validation report
  - [x] Issue table
  - [x] Completeness table
- [x] Write unit tests for WorldValidator

**Acceptance:** ValidateWorldCommand executes, emits signal, UI displays results

### Phase 2: Temporal (Week 2)

- [x] Create `src/services/temporal_analyzer.py`
  - [x] TemporalAnalyzer class
  - [x] `_detect_timeline_gaps()` method
  - [x] `_detect_temporal_conflicts()` method
  - [x] `_analyze_character_lifespans()` method
  - [x] `_resolve_date()` helper (date from relation attrs or event_id)
  - [x] Relations pre-bucketed by target_id for O(R) instead of O(E×R)
- [x] Create AnalyzeTemporalCommand (`src/commands/analysis_commands.py`)
  - [x] Registered in `src/commands/registry.py`
- [x] Add signal to DatabaseWorker
  - [x] `temporal_analysis_complete` signal
  - [x] `analyze_temporal()` method
- [x] Add method to AppCoordinator
  - [x] `analyze_temporal()` method
- [x] UI for temporal results (`src/gui/widgets/temporal_panel.py`)
  - [x] Header label (calendar name, gap count, conflict count)
  - [x] Gap table (Start Date, End Date, Duration, Message)
  - [x] Conflict list (Type, Entity, Date, Message, Suggestion)
  - [x] Lifespan table (Name, Birth, Death, Lifespan, Valid)
- [x] Write unit tests for TemporalAnalyzer (34 tests)
- [x] Write unit tests for TemporalPanel (22 tests)
- [x] Write unit tests for AnalyzeTemporalCommand (8 tests)

**API corrections vs design doc:**

- `db_service.get_all_events()` / `get_all_entities()` / `get_all_relations()` (not repository accessors)
- `db_service.get_active_calendar_config()` returns `CalendarConfig` with `.name` (not `meta_repository`)
- Relations are dicts: `rel["rel_type"]`, `rel["attributes"]` (not Relation objects)
- Relation window keys are `valid_from`/`valid_to` (consistent with TemporalResolver)

**Acceptance:** TemporalAnalyzer detects gaps, conflicts, lifespans; AnalyzeTemporalCommand executes and emits signal; TemporalPanel displays all three tables correctly

### Phase 3: Intelligence (Weeks 3-4)

- [x] Create `src/services/intelligence_analyzer.py`
  - [x] IntelligenceAnalyzer class
  - [x] `_detect_plot_holes()` method
  - [x] `_infer_relations()` method
  - [x] `_generate_lore()` method
  - [x] `_build_plot_hole_prompt()` / `_build_relation_prompt()` / `_build_lore_prompt()` helpers
  - [x] `_parse_plot_hole_response()` / `_parse_relation_response()` / `_parse_lore_response()` parsers
  - [x] `_find_relation_candidates()` with tag-indexed O(T) grouping
  - [x] `_make_audit_entry()` helper (DRY audit log construction)
  - [x] Injectable `provider=None` for testability without real LLM calls
- [x] Create RunIntelligenceAnalysisCommand (`src/commands/analysis_commands.py`)
  - [x] `analysis_type` param serialized in `to_dict`/`from_dict`
  - [x] Registered in `src/commands/registry.py`
- [x] Add signal to DatabaseWorker
  - [x] `intelligence_analysis_complete` signal
  - [x] `run_intelligence_analysis(analysis_type)` slot
- [x] Add method to AppCoordinator
  - [x] `run_intelligence_analysis(analysis_type="all")` (uses `Q_ARG(str, ...)`)
- [x] Prompt templates — built inline via `_build_*_prompt()` methods (no external files needed)
- [x] UI for intelligence results (`src/gui/widgets/intelligence_panel.py`)
  - [x] Header label (model name, counts)
  - [x] Plot holes table (Severity, Entity, Description, Resolution, Confidence)
  - [x] Relation proposals table (Source, Target, Type, Confidence, Reasoning)
  - [x] Lore suggestions table (Gap Start, Gap End, Suggestions)
- [x] Audit logging integration (`audit_log` field in `IntelligenceReport`)
- [x] Write unit tests for IntelligenceAnalyzer (32 tests using `_FakeProvider` stub)
- [x] Write unit tests for IntelligencePanel (26 tests)
- [x] Write unit tests for RunIntelligenceAnalysisCommand (10 tests)

**API corrections vs design doc:**

- `create_provider(provider_id)` from `llm_provider.py` (not `LLMProvider.create()`)
- `provider.generate(prompt)` returns `Dict[str, Any]` with `"text"` key (not raw string)
- `RAGService(db_path: str)` not `RAGService(db_service)` — unused in final impl (prompts built from db_service data)
- Gap boundary fix: `events_before` uses `<=` not `<` (gap.start_date IS the event's lore_date)
- `_MAX_ENTITIES_FOR_PLOT_HOLES`, `_MAX_RELATION_CANDIDATES`, `_MAX_GAPS_FOR_LORE` module-level caps

### Phase 3 Extension: Main App UI Integration

- [x] Add `DOCK_OBJ_ANALYSIS` / `DOCK_TITLE_ANALYSIS` to `src/app/constants.py`
- [x] Create `src/gui/widgets/main_analysis_panel.py` (MainAnalysisPanel)
  - [x] Three trigger buttons (validate_btn, temporal_btn, intelligence_btn)
  - [x] Status label
  - [x] QTabWidget with AnalysisPanel / TemporalPanel / IntelligencePanel
  - [x] `on_validation_complete`, `on_temporal_complete`, `on_intelligence_complete` slots
  - [x] Named tab index constants (`_TAB_VALIDATION`, `_TAB_TIMELINE`, `_TAB_INTELLIGENCE`)
  - [x] Dumb UI — no coordinator reference; wired by ConnectionManager
- [x] Add Analysis dock to `UIManager.setup_docks()` (tabified with entity inspector)
- [x] Instantiate `MainAnalysisPanel` in `main_window._init_widgets_skeleton()`
- [x] Add `connect_analysis_panel()` to `ConnectionManager` and call from `connect_all()`
  - [x] Worker→panel signals with `QueuedConnection`
  - [x] Button→coordinator connections
- [x] Write unit tests for MainAnalysisPanel (19 tests)

**Acceptance:** AI analysis runs, generates insights, audits interactions; all three analysis types accessible from the Analysis Suite dock with live signal wiring

### Phase 4: Polish (Week 5)

- [x] Code review & cleanup
  - [x] Remove redundant `self.setLayout(layout)` from AnalysisPanel and TemporalPanel
  - [x] Extract shared `make_analysis_table()` to `src/gui/widgets/_analysis_utils.py`
  - [x] TemporalPanel and IntelligencePanel now use shared factory (no duplication)
  - [x] Column resize modes: `ResizeToContents` for all non-last columns, `StretchLastSection` for last
- [x] Error handling & fallbacks
  - [x] Buttons disabled while analysis is running (`on_analysis_started`)
  - [x] Buttons re-enabled on `on_*_complete` slots
  - [x] Status label shows "Validating world…" / "Analyzing timeline…" / "Running AI analysis…" on click
  - [x] ThemeManager connection wrapped in try/except in all three sub-panels
- [x] UI refinement & styling
  - [x] `StyleHelper.get_table_widget_style()` added — theme-aware QSS for QTableWidget + QHeaderView
  - [x] All three sub-panels apply table style + section header style + preview-label header style
  - [x] All three sub-panels subscribe to `ThemeManager.theme_changed` for live updates
  - [x] Severity row coloring: CRITICAL=#e74c3c, WARNING=#e67e22, INFO=#3498db (AnalysisPanel + IntelligencePanel)
  - [x] `ANALYSIS_SEVERITY_*_COLOR` constants added to `src/app/constants.py`
  - [x] Status label in MainAnalysisPanel styled with `get_preview_label_style()`
- [x] Temporal date formatting: raw floats replaced with `"Year N"` labels via `_fmt_date()` helper
- [x] Version bump: 0.15.0 → 0.16.0 in `src/app/constants.py`
- [x] Documentation: all new methods have Google-style docstrings
- [ ] User testing (manual)
- [ ] Release notes

**Acceptance:** All 233 Tier 1 unit tests pass, code is clean, UI is polished and theme-aware

---

## SUCCESS CRITERIA

✅ **Implementation is successful when:**

1. All three commands execute without errors
2. Validation detects actual issues in test worlds
3. Temporal analysis finds gaps and conflicts
4. AI analysis generates meaningful insights
5. UI displays reports clearly
6. Audit logging captures all LLM interactions
7. All unit + integration tests pass
8. Code follows ProjektKraken conventions (type hints, docstrings, etc.)
9. No breaking changes to existing features

---

## DEPLOYMENT CHECKLIST

- [ ] All tests pass locally
- [ ] Code review approved
- [ ] Documentation complete
- [ ] User guide written
- [ ] Merge to main
- [ ] Version bump
- [ ] Release notes published

---

**This design document is your roadmap. Follow it step-by-step, testing as you go.**
