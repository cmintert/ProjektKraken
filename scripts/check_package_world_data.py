"""Reject world data and runtime logs in Windows distribution payloads."""

import argparse
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

_RUNTIME_DIRECTORIES = {"worlds", "logs"}
_WORLD_FILE = re.compile(
    r"(?:^world\.json$|\.(?:kraken(?:world)?|sqlite3?)(?:-wal|-shm|-journal)?$)"
)


def runtime_entries(paths: Iterable[str]) -> list[str]:
    """Find runtime paths anywhere in a staging tree or ZIP."""
    matches = []
    for path in paths:
        parts = PurePosixPath(path.replace("\\", "/").casefold()).parts
        if parts and (
            _RUNTIME_DIRECTORIES.intersection(parts) or _WORLD_FILE.search(parts[-1])
        ):
            matches.append(path)
    return matches


def main() -> None:
    """Check the staged package directory or archive and fail on contamination."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    package = parser.parse_args().package
    if package.is_dir():
        matches = runtime_entries(
            path.relative_to(package).as_posix() for path in package.rglob("*")
        )
    else:
        with ZipFile(package) as archive:
            matches = runtime_entries(archive.namelist())
    if matches:
        raise SystemExit(
            f"Package contains {len(matches)} runtime entries. "
            "Rebuild from a clean stage and let first launch create the default world."
        )
    print("Package contains no world data or runtime logs.")


if __name__ == "__main__":
    main()
