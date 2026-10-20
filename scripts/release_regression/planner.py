"""Deterministic exhaustive module allocation, without another test inventory."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

from scripts.release_regression.common import SCHEMA, digest, seal, unseal


def module_name(nodeid: str) -> str:
    """Validate canonical repository-relative test identities."""
    module = nodeid.split("::", 1)[0]
    path = PurePosixPath(module)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in module
        or not module.startswith("tests/")
        or path.suffix != ".py"
        or "::" not in nodeid
    ):
        raise ValueError(f"Unknown test path: {nodeid}")
    return module


def validate(plan: dict[str, Any]) -> None:
    """Prove exact assignment before any subprocess can execute."""
    unseal(plan)
    if plan["inventory_digest"] != digest(plan["inventory"]):
        raise ValueError("Inventory digest mismatch")
    nodes = plan["order"]
    if not nodes or len(set(nodes)) != len(nodes):
        raise ValueError("Empty or duplicate canonical inventory")
    modules: dict[str, list[str]] = {}
    for node in nodes:
        modules.setdefault(module_name(node), []).append(node)
    if modules != plan["modules"]:
        raise ValueError("Module inventory mismatch")
    assigned = [module for shard in plan["shards"] for module in shard]
    if not plan["shards"] or any(not shard for shard in plan["shards"]):
        raise ValueError("Empty required shard")
    if Counter(assigned) != Counter(modules.keys()):
        raise ValueError("Missing, duplicate or unexpected module assignment")
    if set(nodes) != set(plan["inventory"]["tests"]):
        raise ValueError("Canonical inventory drift")
    if plan["inventory"]["counts"]["full"] != len(nodes):
        raise ValueError("Canonical inventory count mismatch")


def build(
    inventory: dict[str, Any],
    order: list[str],
    *,
    sha: str,
    environment: dict[str, Any],
    run: str,
    durations: dict[str, float],
    shards: int = 6,
    collection_skips: list[dict[str, str]] | None = None,
    configuration: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Use stable longest-first scheduling and preserve within-module order."""
    modules: dict[str, list[str]] = {}
    for node in order:
        modules.setdefault(module_name(node), []).append(node)
    if shards < 1 or shards > len(modules):
        raise ValueError("Shard count must fit nonempty module inventory")
    estimates = {
        name: float(durations.get(name, max(5, len(nodes))))
        for name, nodes in modules.items()
    }
    if any(not math.isfinite(x) or x <= 0 for x in estimates.values()):
        raise ValueError("Durations must be finite positive seconds")
    groups: list[list[str]] = [[] for _ in range(shards)]
    totals = [0.0] * shards
    for module in sorted(modules, key=lambda name: (-estimates[name], name)):
        target = min(range(shards), key=lambda index: (totals[index], index))
        groups[target].append(module)
        totals[target] += estimates[module]
    plan = seal(
        {
            "schema": SCHEMA,
            "sha": sha,
            "run": run,
            "environment": environment,
            "inventory": inventory,
            "inventory_digest": digest(inventory),
            "order": order,
            "modules": modules,
            "shards": groups,
            "estimates": estimates,
            "estimated_shard_seconds": totals,
            "unknown_durations": sorted(set(modules) - set(durations)),
            "collection_skips": collection_skips or [],
            "configuration": configuration or {},
        }
    )
    validate(plan)
    return plan


def durations_from_log(content: str) -> dict[str, float]:
    """Extract observed module spans from timestamped Actions pytest output.

    Last-test and teardown time is attributed to the preceding module. The final
    module is omitted because an interrupted log cannot establish its duration.
    """
    from datetime import datetime

    pattern = re.compile(
        r"^(\S+Z)\s+(tests/[^\s:]+\.py)::.*\s"
        r"(?:PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)(?:\s|$)",
        re.MULTILINE,
    )
    result: dict[str, float] = {}
    previous: str | None = None
    start = 0.0
    for match in pattern.finditer(content):
        stamp = datetime.fromisoformat(match[1]).timestamp()
        module = match[2]
        if module == previous:
            continue
        if previous is not None:
            result[previous] = max(0.01, stamp - start)
        previous, start = module, stamp
    return result
