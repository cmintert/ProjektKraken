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


@contextmanager
def staged_markdown_output(
    destination: Path, *, cancelled: Callable[[], bool] = lambda: False
) -> Iterator[tuple[Path, Path]]:
    """Publish Markdown and its image folder, rolling back on ordinary failures."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    assets = destination.with_name(destination.name + ".assets")
    with tempfile.TemporaryDirectory(
        prefix=".kraken-transfer-", dir=destination.parent
    ) as temporary:
        root = Path(temporary)
        output = root / destination.name
        images = root / assets.name
        yield output, images
        if cancelled():
            raise InterruptedError("Transfer cancelled. Existing output is unchanged.")
        previous = root / "previous-assets"
        had_assets = assets.exists()
        published_assets = False
        try:
            if images.exists():
                if had_assets:
                    assets.rename(previous)
                images.rename(assets)
                published_assets = True
            os.replace(output, destination)
        except BaseException:
            if published_assets:
                shutil.rmtree(assets)
            if previous.exists():
                previous.rename(assets)
            raise
