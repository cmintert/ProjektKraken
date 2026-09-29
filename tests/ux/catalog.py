"""Versioned author-facing benchmark tasks and their observable outcomes."""

from __future__ import annotations

from dataclasses import dataclass

CATALOG_VERSION = "1.0"


@dataclass(frozen=True)
class Task:
    """One independently prepared authoring task."""

    id: str
    prompt: str
    success: str

    @property
    def tier(self) -> str:
        """Return the benchmark tier."""
        return self.id[1]


_ROWS = (
    ("KA-01", "Create Tasgillia as a character and record that she belongs to House Tytalus.", "Correct entity and basic fact exist."),
    ("KA-02", "Write a description of Tasgillia, navigate elsewhere, return and correct one sentence.", "Text survives and remains safely editable."),
    ("KA-03", "Create Durenmar as a location and describe it as a covenant in the Black Forest.", "Correct location exists."),
    ("KA-04", "Create House Tytalus as a faction.", "Correct faction exists."),
    ("KA-05", "Organize Tasgillia, House Tytalus and Durenmar as part of the Rhine Tribunal material.", "Useful categorization is created."),
    ("KA-06", "Find Tasgillia again without manually browsing the whole world.", "Correct entity is reached."),
    ("KA-07", "Record that Tasgillia is a member of House Tytalus.", "Correct relation exists."),
    ("KA-08", "Record an association between Tasgillia and Durenmar.", "Correct location relation exists."),
    ("KA-09", "Create Execution of Tasgillia, sometime in 961; exact date unknown.", "Year-only precision is preserved."),
    ("KA-10", "Create a succession event also sometime in 961.", "Second coarse event exists."),
    ("KA-11", "Record that the execution happened before the succession without inventing dates.", "Chronology exists; precision is unchanged."),
    ("KA-12", "Record that Tasgillia's office ends at the succession transition.", "Correct temporal validity exists."),
    ("KA-13", "Record that the successor holds the office from that same transition onward.", "Shared transition is represented."),
    ("KA-14", "Inspect the world before and after succession and determine the office-holder.", "Historical state is understood correctly."),
    ("KA-15", "Determine why Kraken considers the successor to hold the office.", "Provenance is discoverable."),
    ("KA-16", "Create Kalliste and connect her to House Tytalus and relevant events.", "Multiple correct relations exist."),
    ("KA-17", "Correct one historical fact about Kalliste at the point it became true without changing her whole biography.", "Supplying source or state is corrected."),
    ("KA-18", "Place Durenmar and another covenant on the Rhine Tribunal map.", "Spatial state is represented."),
    ("KA-19", "Record a character travelling between two covenants and inspect the character before, during and after travel.", "Temporal trajectory is understandable."),
    ("KA-20", "Introduce a chronology error, discover it, correct it, undo/redo the correction and create a restorable backup.", "Validation, recovery and backup succeed."),
    ("KB-01", "Order three year-only events without assigning exact dates.", "Three-event dependency chain is retained."),
    ("KB-02", "Require a minimum gap between two uncertain events.", "Gap is stored without changing authored precision."),
    ("KB-03", "Make two changes share one event transition.", "End and start refer to the same anchor."),
    ("KB-04", "Record conflicting evidence about one event's date and inspect the conflict.", "Claims remain distinct and conflict is visible."),
    ("KB-05", "Make a relationship begin and end relative to named events.", "Both event-relative boundaries are retained."),
    ("KB-06", "Record an event with only a latest possible date.", "Unknown lower bound is not treated as open or exact."),
    ("KB-07", "Author a year-only event using the fixture's custom calendar.", "Calendar identity and year precision survive reload."),
    ("KB-08", "Resolve two non-commuting changes to one entity using explicit chronology.", "Correct winning value and source are shown."),
    ("KB-09", "Delete an event referenced as a temporal anchor and inspect the result.", "Reference is handled visibly and can be recovered."),
    ("KB-10", "Combine uncertain order, a minimum gap and a shared transition across three events.", "All authored temporal claims remain expressible."),
    ("KC-01", "Find a named character in a world with 25,000 entities and 10,000 events.", "Correct entity is opened without exhaustive browsing."),
    ("KC-02", "Find and inspect a relation in a world with 200,000 relations.", "Correct relation is reached and remains editable."),
    ("KC-03", "Find the intended one of two similarly named people.", "Correct identity is distinguished."),
    ("KC-04", "Find a useful tag among 128 tags and apply it to a person.", "Correct tag is assigned."),
    ("KC-05", "Edit an event with a legacy exact date without changing its precision.", "Exact date remains exact."),
    ("KC-06", "Inspect and repair an imported chronology conflict.", "Issue is discoverable and corrected without discarding unrelated claims."),
    ("KC-07", "Create and date an event with the inspector 360 logical pixels wide.", "Task completes without clipped primary controls."),
    ("KC-08", "Make five linked edits, undo them, then redo them.", "World returns to the expected states at each step."),
    ("KC-09", "Open a map whose image asset is missing and recover navigation.", "Missing asset is explained without losing world access."),
    ("KC-10", "Edit and inspect a multi-leg temporal trajectory.", "Route and timing remain understandable."),
)

TASKS = tuple(Task(*row) for row in _ROWS)
TASK_BY_ID = {task.id: task for task in TASKS}
