"""Immutable offline Help records and shared content identity helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

HELP_SCHEMA = 1
HELP_BUILD_COMMAND = "python -m scripts.build_help"
HELP_INPUT_FILES = (
    "docs/help-topics.json",
    "docs/help-inspection.json",
    "docs/conf.py",
    "pyproject.toml",
    "requirements/docs.txt",
    "scripts/build_help.py",
    "scripts/help_builder.py",
    "src/core/help_bundle.py",
    "src/core/version.py",
)


def file_hash(path: Path) -> str:
    """Return the SHA-256 identity of exact file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    """Fingerprint the complete canonical manual and generation inputs."""
    paths = set(HELP_INPUT_FILES)
    paths.update(
        path.relative_to(root).as_posix()
        for path in (root / "docs/user").rglob("*")
        if path.is_file()
    )
    return {name: file_hash(root / name) for name in sorted(paths)}


@dataclass(frozen=True)
class HelpMetadata:
    """Identity of the source used to generate an installed manual."""

    version: str
    revision: str
    dirty: bool


@dataclass(frozen=True)
class HelpPage:
    """A generated page and its legal navigation fragments."""

    path: str
    title: str
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class HelpTopic:
    """A semantic topic resolved to a generated page and named anchor."""

    id: str
    page: str
    fragment: str
    title: str
    level: str
    related_ids: tuple[str, ...]
    control_excerpt_target: str | None = None


@dataclass(frozen=True)
class HelpSearchDocument:
    """Plain-text section content for a future offline search interface."""

    page: str
    fragment: str
    title: str
    text: str
    topic_ids: tuple[str, ...]
