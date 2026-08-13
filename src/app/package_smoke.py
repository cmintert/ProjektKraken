"""Packaged-application smoke controller used by Windows release automation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication, QLabel

from src.core.logging_config import get_logger
from src.core.paths import get_executable_dir, get_resource_path
from src.core.version import VERSION
from src.gui.dialogs.about_dialog import AboutDialog

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

_PACKAGE_CONTRACT_PATH = "package-contract.json"
logger = get_logger(__name__)


@dataclass(frozen=True)
class PackageSmokeOptions:
    """Parsed internal package-smoke arguments."""

    phase: str
    report_path: Path
    expected_world_id: str | None = None


@dataclass(frozen=True)
class PackageSmokeReport:
    """Serializable result written by one packaged application launch."""

    success: bool
    phase: str
    version: str
    world_id: str
    world_name: str
    world_path: str
    database_path: str
    resources_checked: tuple[str, ...]
    errors: tuple[str, ...]


def parse_package_smoke_options(argv: list[str]) -> PackageSmokeOptions | None:
    """Parse hidden package-smoke arguments while leaving normal startup alone."""
    if "--package-smoke-phase" not in argv:
        return None

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--package-smoke-phase",
        choices=("first-run", "restart"),
        required=True,
    )
    parser.add_argument("--package-smoke-report", type=Path, required=True)
    parser.add_argument("--package-smoke-expected-world-id")
    options, _unknown = parser.parse_known_args(argv[1:])
    if options.package_smoke_phase == "restart" and not (
        options.package_smoke_expected_world_id or ""
    ).strip():
        parser.error("restart smoke requires --package-smoke-expected-world-id")
    return PackageSmokeOptions(
        phase=options.package_smoke_phase,
        report_path=options.package_smoke_report.resolve(),
        expected_world_id=options.package_smoke_expected_world_id,
    )


class PackageSmokeController:
    """Validate one real packaged startup and terminate it deterministically."""

    def __init__(
        self,
        window: "MainWindow",
        options: PackageSmokeOptions,
    ) -> None:
        """Initialize the smoke controller for a running main window."""
        self._window = window
        self._options = options
        self._completed = False

    def start(self) -> None:
        """Wait for worker initialization or validate an already-ready window."""
        logger.info("Package smoke %s phase started", self._options.phase)
        manager = self._window.worker_manager
        manager.package_smoke_callback = self.on_database_ready
        if manager.database_initialized is not None:
            self.on_database_ready(bool(manager.database_initialized))

    def on_database_ready(self, success: bool) -> None:
        """Collect evidence after the existing GUI initialization callback."""
        if self._completed:
            return
        logger.info("Package smoke received database readiness: %s", success)
        errors = [] if success else ["Database worker initialization failed."]
        try:
            report = self._collect_report(errors)
        except Exception as exc:
            logger.exception("Package smoke evidence collection failed")
            report = self._failure_report(f"Smoke evidence collection failed: {exc}")
        self._finish(report, 0 if report.success else 1)

    def _failure_report(self, error: str) -> PackageSmokeReport:
        world = self._window.current_world
        return PackageSmokeReport(
            success=False,
            phase=self._options.phase,
            version=VERSION,
            world_id=str(getattr(world, "id", "") or ""),
            world_name=str(getattr(world, "name", "") or ""),
            world_path=str(getattr(world, "path", "") or ""),
            database_path=str(getattr(world, "db_path", "") or ""),
            resources_checked=(),
            errors=(error,),
        )

    def _collect_report(self, errors: list[str]) -> PackageSmokeReport:
        logger.info("Collecting packaged application smoke evidence")
        world = self._window.current_world
        world_id = str(getattr(world, "id", "") or "")
        world_name = str(getattr(world, "name", "") or "")
        world_path = Path(getattr(world, "path", "")) if world else Path()
        database_path = Path(getattr(world, "db_path", "")) if world else Path()

        if not world_id:
            errors.append("No active world was loaded.")
        if self._options.phase == "restart" and (
            world_id != self._options.expected_world_id
        ):
            errors.append(
                "Restart opened world ID "
                f"{world_id!r}; expected {self._options.expected_world_id!r}."
            )
        if not world_path.is_dir():
            errors.append(f"World directory is missing: {world_path}")
        if world and not world.manifest_path.is_file():
            errors.append(f"World manifest is missing: {world.manifest_path}")
        if not database_path.is_file():
            errors.append(f"World database is missing: {database_path}")
        if world and not world.assets_path.is_dir():
            errors.append(f"World assets directory is missing: {world.assets_path}")
        logger.info("Package smoke world evidence collected")

        resources_checked: tuple[str, ...] = ()
        contract_path = Path(get_resource_path(_PACKAGE_CONTRACT_PATH))
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            resources_checked = tuple(contract["smoke_resources"])
        except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"Package contract is unreadable: {exc}")
        missing_resources = [
            relative
            for relative in resources_checked
            if not Path(get_resource_path(relative)).is_file()
        ]
        errors.extend(f"Bundled resource is missing: {path}" for path in missing_resources)
        logger.info("Package smoke resource evidence collected")

        build_info_path = get_executable_dir() / "build-info.json"
        if not build_info_path.is_file():
            errors.append(f"Package build metadata is missing: {build_info_path}")
        else:
            try:
                build_info = json.loads(build_info_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"Package build metadata is unreadable: {exc}")
            else:
                if build_info.get("version") != VERSION:
                    errors.append(
                        "Package build metadata version does not match runtime: "
                        f"{build_info.get('version')!r} != {VERSION!r}."
                    )
        logger.info("Package smoke build metadata evidence collected")

        logger.info("Constructing About dialog for version evidence")
        about = AboutDialog(self._window)
        about_text = {label.text() for label in about.findChildren(QLabel)}
        about.close()
        about.deleteLater()
        if f"Version {VERSION}" not in about_text:
            errors.append(f"About dialog does not show Version {VERSION}.")

        logger.info("Package smoke evidence collection completed")

        return PackageSmokeReport(
            success=not errors,
            phase=self._options.phase,
            version=VERSION,
            world_id=world_id,
            world_name=world_name,
            world_path=str(world_path.resolve()) if world else "",
            database_path=str(database_path.resolve()) if world else "",
            resources_checked=resources_checked,
            errors=tuple(errors),
        )

    def _finish(self, report: PackageSmokeReport, exit_code: int) -> None:
        self._completed = True
        self._window.worker_manager.package_smoke_callback = None
        self._options.report_path.parent.mkdir(parents=True, exist_ok=True)
        self._options.report_path.write_text(
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        logger.info("Package smoke report written; closing application")
        self._window.close()
        QApplication.exit(exit_code)
