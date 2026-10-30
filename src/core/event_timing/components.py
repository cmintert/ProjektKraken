"""Partition compiled timing facts without changing their evidence or ordering."""

from dataclasses import replace

from src.core.event_timing.compiler import CompiledTiming
from src.core.event_timing.constraints import Cancel, checkpoint


def component_problems(
    problem: CompiledTiming,
    components: list[tuple[str, ...]],
    cancel: Cancel | None,
) -> list[CompiledTiming]:
    """Index local solver inputs once per compiled/quarantined generation.

    Views retain the shared compilation metadata but own their local collections.
    Edges follow their source owner; the branch builder still checks both ends,
    while infeasibility diagnostics retain the original source-owned rules.
    """
    groups = []
    owners = {}
    for index, nodes in enumerate(components):
        checkpoint(cancel)
        groups.append(
            replace(
                problem,
                definitions={node: problem.definitions[node] for node in nodes},
                evidence={},
                domains={},
                edges=[],
                calendars=[],
                invalid=set(),
                issues=[],
            )
        )
        owners.update(dict.fromkeys(nodes, index))
    for node, evidence in problem.evidence.items():
        groups[owners[node]].evidence[node] = evidence
    for node, ranges in problem.domains.items():
        groups[owners[node]].domains[node] = ranges
    for edge in problem.edges:
        groups[owners[edge.source]].edges.append(edge)
    for node, definition in problem.calendars:
        groups[owners[node]].calendars.append((node, definition))
    for node in problem.invalid:
        if node in owners:
            groups[owners[node]].invalid.add(node)
    for issue in problem.issues:
        for index in {owners[node] for node in issue.endpoints if node in owners}:
            groups[index].issues.append(issue)
    checkpoint(cancel)
    return groups
