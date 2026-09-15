import json
from pathlib import Path

from src.performance.reporting import write_reports


def test_reports_are_measurement_only_and_do_not_update_baseline(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline = {
        "environment": {"platform": "other"},
        "metrics": {
            "scenario": {"unit": "ms", "summary": {"median": 10.0}}
        },
    }
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    original_baseline = baseline_path.read_bytes()
    manifest = {
        "run_id": "test",
        "mode": "quick",
        "target": "source",
        "environment": {"platform": "current"},
        "integrity": {"success": True},
    }

    result = write_reports(
        tmp_path,
        manifest,
        {"scenario": {"unit": "ms", "samples": [20.0, 21.0]}},
        compare_path=baseline_path,
    )

    assert result["label"] == "MEASUREMENT ONLY"
    assert result["regressions"][0]["metric"] == "scenario"
    assert "Environment differs" in result["comparison_warning"]
    assert baseline_path.read_bytes() == original_baseline
    assert (tmp_path / "summary.md").is_file()
    assert (tmp_path / "metrics.json").is_file()
    assert (tmp_path / "run-manifest.json").is_file()

