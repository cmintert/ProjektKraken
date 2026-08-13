"""Generate the temporary multi-resolution Windows executable icon."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

_ICON_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256))


def generate_icon(source: Path, destination: Path) -> None:
    """Convert the canonical application image into a multi-size ICO file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(destination, format="ICO", sizes=_ICON_SIZES)


def main() -> None:
    """Parse paths and generate the Windows icon."""
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    generate_icon(args.source, args.destination)


if __name__ == "__main__":
    main()
