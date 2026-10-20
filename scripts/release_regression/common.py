"""Versioned evidence, source identity and environment provenance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 1


def digest(value: Any) -> str:
    """Hash canonical JSON without platform-dependent formatting."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_hash(path: Path) -> str:
    """Hash an evidence file without loading large logs into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path) -> Any:
    """Read JSON evidence, rejecting ambiguous duplicate keys."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text("utf-8"), object_pairs_hook=unique)


def write(path: Path, value: Any) -> None:
    """Atomically replace a report, including after a failed subprocess."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def git(*args: str) -> str:
    """Inspect this checkout with Windows safe-directory handling."""
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def source_sha() -> str:
    """Require clean committed source; dirty rehearsals cannot certify releases."""
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Release verification requires a clean committed checkout")
    return git("rev-parse", "HEAD")


def environment() -> dict[str, Any]:
    """Describe dependencies and native rendering inputs for strict recovery."""
    from scripts.release_regression.process_tree import ensure_runtime

    ensure_runtime()
    from PySide6 import QtCore

    native = ""
    if sys.platform == "linux":
        native = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Package}=${Version}\n"], text=True
        )
    return {
        "python": platform.python_version(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "os": platform.platform(),
        "image": os.environ.get("ImageVersion", "local"),
        "qt": QtCore.qVersion(),
        "packages": sorted(
            [dist.metadata["Name"].lower(), dist.version]
            for dist in importlib.metadata.distributions()
        ),
        "native_packages": native,
        "fonts": font_inventory(),
        "qt_environment": {
            key: os.environ.get(key, "")
            for key in (
                "QT_QPA_PLATFORM",
                "QT_OPENGL",
                "QT_STYLE_OVERRIDE",
                "QT_FONT_DPI",
                "LANG",
                "LC_ALL",
                "TZ",
            )
        },
    }


@lru_cache(maxsize=4096)
def font_hash(path: str, size: int, modified_ns: int) -> str:
    """Reuse font hashes only while the file identity remains unchanged."""
    return file_hash(Path(path))


def font_inventory() -> dict[str, str]:
    """Include user-installed fonts, which package versions cannot describe."""
    if sys.platform == "linux":
        names = subprocess.check_output(["fc-list", "--format=%{file}\n"], text=True)
        paths = {Path(name) for name in names.splitlines() if name}
    elif sys.platform == "win32":
        directories = [
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts",
        ]
        paths = {
            path
            for directory in directories
            if directory.exists()
            for path in directory.iterdir()
            if path.suffix.lower() in {".ttf", ".otf", ".ttc", ".fon"}
        }
    else:
        raise ValueError("Release font provenance is supported on Linux and Windows")
    return {
        str(path): font_hash(str(path), path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(paths)
    }


def configuration() -> dict[str, str]:
    """Expose the tracked collection, dependency and coverage inputs in evidence."""
    paths = [
        ROOT / "pytest.ini",
        ROOT / "pyproject.toml",
        ROOT / "requirements.txt",
        ROOT / "scripts/release_regression/coverage.ini",
    ]
    paths.extend(sorted((ROOT / "requirements").glob("*.txt")))
    return {path.relative_to(ROOT).as_posix(): file_hash(path) for path in paths}


def provenance(
    plan: dict[str, Any], *, expected_environment: dict[str, Any] | None = None
) -> None:
    """Check committed inputs and, within one job, its recorded environment.

    Hosted matrix jobs may land on different runner images during a rollout.
    Their complete environments are retained per shard and checked per attempt.
    """
    if (
        source_sha() != plan["sha"]
        or configuration() != plan["configuration"]
        or (expected_environment is not None and environment() != expected_environment)
    ):
        raise ValueError("Candidate or environment changed; start a fresh complete run")


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Attach a digest to an immutable manifest or report."""
    return {**value, "digest": digest(value)}


def unseal(value: dict[str, Any]) -> None:
    """Validate the schema and content digest before using evidence."""
    payload = {key: item for key, item in value.items() if key != "digest"}
    if value.get("schema") != SCHEMA or digest(payload) != value.get("digest"):
        raise ValueError("Unsupported schema or corrupt evidence digest")
