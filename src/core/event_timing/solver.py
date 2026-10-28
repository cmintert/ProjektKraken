"""World endpoint solving, disjunctive feasibility and evidence projection."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

from src.core.calendar import CalendarConverter
from src.core.event_timing.calendar_domains import CalendarPiece, calendar_pieces
from src.core.event_timing.compiler import CompiledTiming, _quarantine, compile_timing
from src.core.event_timing.constraints import (
    ZERO,
    Cancel,
    ConstraintBranch,
    checkpoint,
    merge_intervals,
)
from src.core.event_timing.resolution import (
    EndpointResolution,
    TemporalWorldResolution,
    TimingIssue,
)
from src.core.events import Event
from src.core.temporal_expression import ResolvedTemporalBounds


def _components(problem: CompiledTiming) -> list[tuple[str, ...]]:
    pending = set(problem.definitions)
    result = []
    while pending:
        stack = [min(pending)]
        found: set[str] = set()
        while stack:
            node = stack.pop()
            if node in found:
                continue
            found.add(node)
            stack.extend(problem.neighbors[node] - found)
        pending -= found
        result.append(tuple(sorted(found)))
    return result


def _domain_branches(
    problem: CompiledTiming, component: tuple[str, ...], cancel: Cancel | None
) -> list[ConstraintBranch]:
    edges = tuple(
        edge
        for edge in problem.edges
        if edge.source in component and edge.target in component
    )
    choices = [
        tuple(item.constraints(node, f"evidence:{node}") for item in ranges)
        for node, ranges in problem.domains.items()
        if node in component
    ]
    common = [
        edge
        for alternatives in choices
        if len(alternatives) == 1
        for edge in alternatives[0]
    ]
    choices = [alternatives for alternatives in choices if len(alternatives) != 1]
    if any(not alternatives for alternatives in choices):
        return []
    base = ConstraintBranch(component, (*edges, *common), cancel)
    if not base.feasible:
        return []
    branches = []
    pending = [(0, base)]
    while pending:
        checkpoint(cancel)
        index, branch = pending.pop()
        if index == len(choices):
            branches.append(branch)
            continue
        for alternative in reversed(choices[index]):
            candidate = branch.with_query(alternative)
            if candidate.feasible:
                pending.append((index + 1, candidate))
    return branches


def _calendar_branches(
    problem: CompiledTiming,
    component: tuple[str, ...],
    bases: list[ConstraintBranch],
    converter: CalendarConverter | None,
    cancel: Cancel | None,
) -> tuple[list[ConstraintBranch], set[str]]:
    transforms = [
        (node, definition)
        for node, definition in problem.calendars
        if node in component and node not in problem.invalid
    ]
    if not transforms:
        return bases, set()
    order = {node: index for index, node in enumerate(problem.evidence)}
    transforms.sort(key=lambda item: order[item[0]])

    def pieces_at(index: int, branch: ConstraintBranch) -> Iterator[CalendarPiece]:
        node, definition = transforms[index]
        return calendar_pieces(
            node,
            definition,
            (branch.difference(ZERO, definition.source),),
            converter,
            cancel,
        )

    result = []
    for base in bases:
        stack = [(0, base, pieces_at(0, base), frozenset[str]())]
        while stack:
            checkpoint(cancel)
            index, parent, choices, previous_invalid = stack[-1]
            piece = next(choices, None)
            if piece is None:
                stack.pop()
                continue
            branch = parent.with_query(piece.edges)
            if not branch.feasible:
                continue
            invalid = previous_invalid | ({piece.invalid} if piece.invalid else set())
            if index + 1 == len(transforms):
                if invalid:
                    return [], set(invalid)
                result.append(branch)
            else:
                stack.append(
                    (
                        index + 1,
                        branch,
                        pieces_at(index + 1, branch),
                        frozenset(invalid),
                    )
                )
    return result, set()


def _project(
    problem: CompiledTiming,
    result: TemporalWorldResolution,
    component: tuple[str, ...],
    branches: list[ConstraintBranch],
    invalid: set[str],
) -> None:
    existing = any(
        set(issue.endpoints) & set(component) for issue in problem.issues
    ) or any(node in problem.invalid for node in component)
    if not branches and not existing and not invalid:
        rules = tuple(
            sorted(
                {
                    edge.rule
                    for edge in problem.edges
                    if edge.source in component and edge.rule
                }
            )
        )
        result.issues.append(
            TimingIssue(
                "infeasible",
                component,
                "No interpretation satisfies these Event intervals and chronology rules together.",
                rules,
            )
        )
    for node in sorted(invalid):
        result.issues.append(
            TimingIssue(
                "calendar_offset",
                (node,),
                "The calendar offset cannot map every otherwise possible source date.",
            )
        )
    verified = bool(branches) and not invalid and not existing
    result.branches[component] = tuple(branches) if verified else ()
    facts = sorted(
        {
            f"{edge.rule}|{edge.source}|{edge.target}|{edge.limit}|{edge.strict}"
            for branch in branches
            for edge in branch.edges
        }
    )
    network = hashlib.sha256("\n".join(facts).encode()).hexdigest()
    rules = (
        f"network:{network}",
        *sorted(
            {edge.rule for branch in branches for edge in branch.edges if edge.rule}
        ),
    )
    preferences = {
        node: evidence.soft_start
        for node, evidence in problem.evidence.items()
        if node in component
        and evidence.soft_start is not None
        and (evidence.hard_start is None or evidence.hard_end is None)
    }
    placement = branches[0].placement(preferences) if verified else {}
    for node in component:
        authored = problem.evidence.get(
            node, ResolvedTemporalBounds(error="Endpoint dependencies contain a cycle.")
        )
        ranges = (
            merge_intervals(branch.difference(ZERO, node) for branch in branches)
            if verified
            else ()
        )
        error = authored.error
        if node in problem.invalid:
            error = error or "This endpoint depends on unresolved or cyclic timing."
        if node in invalid:
            error = "The calendar offset cannot map every possible source date."
        elif ranges and error and problem.definitions[node].kind == "event":
            error = None
        result.endpoints[node] = EndpointResolution(
            node,
            authored,
            ranges,
            rules,
            error,
            verified,
            float(placement[node]) if node in placement else None,
        )
        result.components[node] = component


def resolve_world(
    events: list[Event],
    converter: CalendarConverter | None = None,
    cancel: Cancel | None = None,
) -> TemporalWorldResolution:
    """Solve detached authored facts, retaining invalid worlds for local repair."""
    problem = compile_timing(events, converter, cancel)
    while True:
        result = TemporalWorldResolution(
            problem.fingerprint, issues=list(problem.issues)
        )
        result.calendar_json = converter._config.to_json() if converter else None
        invalid_calendars: set[str] = set()
        for component in _components(problem):
            checkpoint(cancel)
            bases = _domain_branches(problem, component, cancel)
            branches, invalid = _calendar_branches(
                problem, component, bases, converter, cancel
            )
            invalid_calendars.update(invalid)
            _project(problem, result, component, branches, invalid)
        if not invalid_calendars:
            break
        problem.issues.extend(
            issue
            for issue in result.issues
            if issue.code == "calendar_offset"
            and set(issue.endpoints) & invalid_calendars
        )
        problem.invalid.update(invalid_calendars)
        _quarantine(problem)
    for event in events:
        start, end = f"event:{event.id}", f"event:{event.id}:end"
        if start not in result.endpoints:
            error = next(
                (issue.message for issue in problem.issues if start in issue.endpoints),
                "Unsupported timing",
            )
            result.endpoints[start] = EndpointResolution(
                start, ResolvedTemporalBounds(), error=error, verified=False
            )
        if end not in result.endpoints:
            result.endpoints[end] = EndpointResolution(
                end, ResolvedTemporalBounds(), error="This event has no authored end."
            )
    return result
