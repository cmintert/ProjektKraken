"""Machine-readable and human-readable performance reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.performance.statistics import compare_metrics, summarize


def normalize_metrics(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    """Attach stable summaries while retaining raw samples."""
    normalized: dict[str, Any] = {}
    for name, value in raw_metrics.items():
        if isinstance(value, dict) and isinstance(value.get("samples"), list):
            normalized[name] = {
                **value,
                "summary": summarize(value["samples"]),
            }
        else:
            normalized[name] = value
    return normalized


def write_reports(
    run_root: Path,
    manifest: dict[str, Any],
    raw_metrics: dict[str, Any],
    *,
    compare_path: Path | None = None,
) -> dict[str, Any]:
    """Write the three canonical measurement-only report artifacts."""
    metrics = {
        "label": "MEASUREMENT ONLY",
        "schema_version": 1,
        "environment": manifest.get("environment", {}),
        "metrics": normalize_metrics(raw_metrics),
    }
    regressions: list[dict[str, Any]] = []
    comparison_warning: str | None = None
    if compare_path is not None:
        baseline = json.loads(compare_path.read_text(encoding="utf-8"))
        regressions = compare_metrics(metrics, baseline)
        current_environment = manifest.get("environment", {})
        baseline_environment = baseline.get("environment", {})
        keys = ("platform", "processor", "logical_cpu_count", "power_state")
        changed = [
            key
            for key in keys
            if baseline_environment.get(key) not in (None, current_environment.get(key))
        ]
        if changed:
            comparison_warning = (
                "Environment differs from the comparison report: "
                + ", ".join(changed)
            )
    metrics["regressions"] = regressions
    if comparison_warning:
        metrics["comparison_warning"] = comparison_warning

    metrics_path = run_root / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_root / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_root / "summary.md").write_text(
        _render_summary(manifest, metrics), encoding="utf-8"
    )
    return metrics


def _render_summary(manifest: dict[str, Any], metrics: dict[str, Any]) -> str:
    lines = [
        "# ProjektKraken Performance Measurement",
        "",
        "> **MEASUREMENT ONLY.** This report does not select or apply optimizations.",
        "",
        f"- Run: `{manifest.get('run_id', 'unknown')}`",
        f"- Target: `{manifest.get('target', 'unknown')}`",
        f"- Mode: `{manifest.get('mode', 'unknown')}`",
        f"- Integrity passed: `{manifest.get('integrity', {}).get('success', False)}`",
        "",
        "## Metrics",
        "",
        "| Metric | Unit | Median | p95 | p99 | Samples |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, metric in sorted(metrics.get("metrics", {}).items()):
        if not isinstance(metric, dict) or "summary" not in metric:
            continue
        summary = metric["summary"]
        lines.append(
            f"| {name} | {metric.get('unit', '')} | "
            f"{summary.get('median', 0):.3f} | {summary.get('p95', 0):.3f} | "
            f"{summary.get('p99', 0):.3f} | {summary.get('count', 0)} |"
        )
    regressions = metrics.get("regressions", [])
    lines.extend(["", "## Comparison", ""])
    warning = metrics.get("comparison_warning")
    if warning:
        lines.append(f"- Warning: {warning}")
    if regressions:
        for regression in regressions:
            lines.append(
                "- Regression: "
                f"`{regression['metric']}` +{regression['delta_ms']:.3f} ms "
                f"({regression['relative_change']:.1%})"
            )
    else:
        lines.append("- No threshold-exceeding comparison regressions recorded.")
    warnings = manifest.get("warnings", [])
    if warnings:
        lines.extend(["", "## Measurement warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)
