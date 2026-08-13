"""Tests for the internal packaged-application smoke contract."""

import json
from pathlib import Path

import pytest

from src.app.package_smoke import PackageSmokeOptions, parse_package_smoke_options


def test_parse_package_smoke_first_run(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    options = parse_package_smoke_options(
        [
            "ProjektKraken.exe",
            "--package-smoke-phase",
            "first-run",
            "--package-smoke-report",
            str(report),
        ]
    )

    assert options == PackageSmokeOptions(
        phase="first-run",
        report_path=report.resolve(),
        expected_world_id=None,
    )


def test_parse_package_smoke_restart_requires_world_id(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_package_smoke_options(
            [
                "ProjektKraken.exe",
                "--package-smoke-phase",
                "restart",
                "--package-smoke-report",
                str(tmp_path / "report.json"),
            ]
        )


def test_package_contract_paths_exist_in_checkout() -> None:
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "packaging/windows/package-contract.json").read_text(encoding="utf-8")
    )

    for resource in contract["smoke_resources"]:
        assert (root / resource).is_file(), resource


def test_package_contract_forbids_development_tooling() -> None:
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "packaging/windows/package-contract.json").read_text(encoding="utf-8")
    )

    assert {"pytest", "ruff", "mypy", "sphinx", "tests"}.issubset(
        contract["forbidden_internal_directories"]
    )
    assert contract["strip_and_forbid_recursive_directories"] == ["tests"]
