from pathlib import Path

from src.performance.probe import parse_performance_probe_options
from src.performance.runner import build_parser


def test_probe_options_are_absent_during_normal_startup() -> None:
    assert parse_performance_probe_options(["ProjektKraken.exe"]) is None


def test_probe_options_parse_internal_runner_contract(tmp_path: Path) -> None:
    options = parse_performance_probe_options(
        [
            "ProjektKraken.exe",
            "--performance-probe-report",
            str(tmp_path / "report.json"),
            "--performance-probe-world",
            str(tmp_path / "world"),
            "--performance-probe-settings",
            str(tmp_path / "settings"),
            "--performance-probe-profile",
            "standard",
            "--performance-probe-repetitions",
            "2",
        ]
    )

    assert options is not None
    assert options.profile == "standard"
    assert options.repetitions == 2
    assert options.scrub_positions == 300
    assert options.playback_seconds == 60.0


def test_public_runner_requires_manual_mode_and_target() -> None:
    options = build_parser().parse_args(["--quick", "--target", "source"])

    assert options.quick is True
    assert options.full is False
    assert options.target == "source"
