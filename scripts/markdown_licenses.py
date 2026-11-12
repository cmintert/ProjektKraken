"""Collect exact installed Markdown dependency notices for frozen distribution."""

from __future__ import annotations

from importlib.metadata import distribution
from pathlib import Path

DISTRIBUTIONS = ("markdown-it-py", "mdurl", "linkify-it-py", "mdit-py-plugins")


def collect_markdown_licenses(destination: Path) -> Path:
    """Copy every shipped licence/notice file and fail on missing attribution."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in DISTRIBUTIONS:
        package = distribution(name)
        notices = [
            path
            for path in package.files or ()
            if path.name.upper().startswith(("LICENSE", "LICENCE", "NOTICE", "COPYING"))
        ]
        if not notices:
            raise ValueError(f"Missing licence files for {name} {package.version}")
        parts = [f"{name} {package.version}\n"]
        for path in sorted(notices):
            parts.append(f"\n--- {path.name} ---\n")
            parts.append(package.locate_file(path).read_text(encoding="utf-8"))
        (destination / f"{name}.txt").write_text("".join(parts), encoding="utf-8")
    return destination
