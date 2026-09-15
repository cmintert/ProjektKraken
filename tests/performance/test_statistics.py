from src.performance.statistics import compare_metrics, summarize


def test_summarize_reports_interpolated_percentiles() -> None:
    result = summarize([1.0, 2.0, 3.0, 4.0])

    assert result == {
        "count": 4,
        "min": 1.0,
        "max": 4.0,
        "median": 2.5,
        "p50": 2.5,
        "p95": 3.8499999999999996,
        "p99": 3.9699999999999998,
    }


def test_comparison_requires_relative_and_absolute_thresholds() -> None:
    baseline = {
        "metrics": {
            "slow": {"unit": "ms", "summary": {"median": 100.0}},
            "small": {"unit": "ms", "summary": {"median": 1.0}},
        }
    }
    current = {
        "metrics": {
            "slow": {"unit": "ms", "summary": {"median": 120.0}},
            "small": {"unit": "ms", "summary": {"median": 2.0}},
        }
    }

    regressions = compare_metrics(current, baseline)

    assert [item["metric"] for item in regressions] == ["slow"]

