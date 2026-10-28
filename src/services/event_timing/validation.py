"""Adapt joint timing diagnostics to the existing world validation presentation."""

from src.core.analysis import IssueType, SeverityLevel, ValidationIssue
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.events import Event


def timing_issues(
    events: list[Event], resolution: TemporalWorldResolution
) -> list[ValidationIssue]:
    """Expose structural and global feasibility defects, not just numeric caches."""
    names = {event.id: event.name for event in events}
    result = []
    for issue in resolution.issues:
        identities = sorted(
            {
                node.removeprefix("event:").removesuffix(":end")
                for node in issue.endpoints
            }
        )
        identity = identities[0] if identities else ""
        result.append(
            ValidationIssue(
                severity=SeverityLevel.CRITICAL
                if issue.code == "infeasible"
                else SeverityLevel.WARNING,
                issue_type=IssueType.INVALID_DATE,
                object_id=identity,
                object_type="event",
                object_name=names.get(identity, "Event timing"),
                message=issue.message,
                suggestion="Review Event date sources, ends and chronology. Authored evidence is retained.",
                related_ids=identities,
                fingerprint="event-timing:"
                + issue.code
                + ":"
                + ",".join(issue.endpoints),
            )
        )
    return result
