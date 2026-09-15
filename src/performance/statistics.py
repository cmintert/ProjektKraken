"""Stable statistics and report comparison helpers."""

from __future__ import annotations

import math
import statistics
from typing import Any, Iterable


def percentile(samples: list[float], percentage: float) -> float:
    """Return an interpolated percentile for sorted numeric samples."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    position = (len(ordered) - 1) * percentage
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(samples: Iterable[float]) -> dict[str, float | int]:
    """Summarize one measurement series without hiding its sample count."""
    values = [float(value) for value in samples]
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
    }


def compare_metrics(
    current: dict[str, Any],
    baseline: dict[str, Any],
    relative_threshold: float = 0.15,
    absolute_floor_ms: float = 5.0,
) -> list[dict[str, Any]]:
    """Identify timing regressions that exceed relative and absolute limits."""
    regressions: list[dict[str, Any]] = []
    current_metrics = current.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    for name, current_metric in current_metrics.items():
        if name not in baseline_metrics or current_metric.get("unit") != "ms":
            continue
        current_median = float(current_metric.get("summary", {}).get("median", 0.0))
        baseline_median = float(
            baseline_metrics[name].get("summary", {}).get("median", 0.0)
        )
        if baseline_median <= 0:
            continue
        delta = current_median - baseline_median
        ratio = delta / baseline_median
        if delta >= absolute_floor_ms and ratio >= relative_threshold:
            regressions.append(
                {
                    "metric": name,
                    "baseline_median_ms": baseline_median,
                    "current_median_ms": current_median,
                    "delta_ms": delta,
                    "relative_change": ratio,
                }
            )
    return regressions
