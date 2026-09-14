"""Staged file output shared by transfer adapters."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def staged_output(
    destination: Path,
    *,
    directory: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
) -> Iterator[Path]:
    """Publish a complete output and restore the old destination on failure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".kraken-transfer-", dir=destination.parent
    ) as temporary:
        root = Path(temporary)
        stage = root / ("output" if directory else destination.name)
        if directory:
            stage.mkdir()
        yield stage
        if cancelled():
            raise InterruptedError("Transfer cancelled. Existing output is unchanged.")
        if directory and destination.exists():
            previous = root / "previous"
            destination.rename(previous)
            try:
                stage.rename(destination)
            except BaseException:
                previous.rename(destination)
                raise
            shutil.rmtree(previous)
        else:
            os.replace(stage, destination)
