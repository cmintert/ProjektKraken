"""Fail-closed native screenshot review required independently of simulation."""

import hashlib
import json
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

REQUIRED_SCALES = (1.0, 1.25, 1.5, 2.0)
REQUIRED_TEXT_SCALE = 2.0


def presentation_fingerprint(root: Path) -> str:
    """Identify the exact presentation sources and theme resources reviewed."""
    paths = [
        *root.joinpath("src/gui").rglob("*.py"),
        root / "src/core/theme_manager.py",
        root / "src/app/ui_manager.py",
        root / "src/app/main_window.py",
        root / "src/resources/main.qss",
        root / "themes.json",
    ]
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def native_review_failures(path: Path, root: Path, surfaces: Any) -> list[str]:
    """Require human-approved native records for every surface at every OS scale."""
    if not path.is_file():
        return ["Native Windows screenshot review manifest is missing"]
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
        if (
            review.get("status") != "approved"
            or not review.get("reviewer")
            or not review.get("reviewed_at")
        ):
            return ["Native Windows screenshot review is pending"]
        if review.get("presentation_fingerprint") != presentation_fingerprint(root):
            return [
                "Native screenshot review does not match current presentation sources"
            ]
        records = review.get("records", [])
        approved = set()
        for record in records:
            screenshot = path.parent / record.get("screenshot", "")
            if (
                record.get("method") != "native-windows"
                or record.get("outcome") != "pass"
                or not screenshot.is_file()
            ):
                continue
            if hashlib.sha256(screenshot.read_bytes()).hexdigest() != record.get(
                "sha256"
            ):
                continue
            image = QImage(str(screenshot))
            if image.isNull() or list(image.size().toTuple()) != record.get(
                "physical_size"
            ):
                continue
            if (
                record.get("text_scale") != REQUIRED_TEXT_SCALE
                or not record.get("long_labels")
                or not record.get("states_reviewed")
            ):
                continue
            if not all(
                record.get(field)
                for field in (
                    "requested_logical_size",
                    "actual_logical_size",
                    "physical_size",
                    "fonts",
                    "theme",
                    "windows_display_settings",
                )
            ):
                continue
            approved.add((record.get("surface"), record.get("os_scale")))
        return [
            f"Missing native reviewed evidence: {surface.key} at OS scale {scale:g}"
            for surface in surfaces
            for scale in REQUIRED_SCALES
            if (surface.key, scale) not in approved
        ]
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return [f"Invalid native screenshot review manifest: {error}"]
