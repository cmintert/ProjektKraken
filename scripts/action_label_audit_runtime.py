"""Bound local audit resource use without reducing release verification."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def audit_slot(path: Path) -> Iterator[None]:
    """Prevent overlapping render audits; OS locks release after a crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        if path.stat().st_size == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def write_streamed_report(
    destination: Path, metadata: dict[str, Any], records_path: Path
) -> tuple[int, int]:
    """Retain every measured record while holding only one snapshot in RAM."""
    count = failures = 0
    header = json.dumps(metadata, indent=2)
    with destination.open("w", encoding="utf-8") as output:
        output.write(header.rstrip()[:-1].rstrip())
        output.write(",\n" if metadata else "\n")
        output.write('  "records": [\n')
        with records_path.open(encoding="utf-8") as records:
            for line in records:
                record = json.loads(line)
                if count:
                    output.write(",\n")
                output.write("    " + line.strip())
                count += 1
                failures += len(record["failures"])
        output.write("\n  ]\n}\n")
    return count, failures
