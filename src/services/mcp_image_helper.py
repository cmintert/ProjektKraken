"""Isolated raster-only preview encoder. Input is an internally resolved asset job."""

import base64
import io
import json
import sys
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

MAX_PIXELS = 64_000_000
MAX_ENCODED_IMAGE = 450_000


def preview(job: dict[str, Any]) -> dict[str, Any]:
    """Strip metadata and cap source size, decoded pixels and output dimensions."""
    path = Path(job["path"])
    root = Path(job["root"]).resolve()
    resolved = path.resolve()
    if (
        not resolved.is_relative_to(root / "assets")
        or resolved.stat().st_size > 64 * 1024 * 1024
    ):
        raise ValueError("Asset outside limits")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(resolved) as source:
            if source.format not in {"PNG", "JPEG", "WEBP", "BMP", "GIF", "TIFF"}:
                raise ValueError("Unsupported image format")
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("Pixel limit")
            image = ImageOps.exif_transpose(source).convert("RGBA")
    original = image.size
    crop = job.get("crop")
    if crop is not None:
        image = image.crop(
            tuple(
                round(value * original[index % 2]) for index, value in enumerate(crop)
            )
        )
    edge = 512 if crop is not None else 1024
    image.thumbnail((edge, edge))
    while True:
        # A new image carries no EXIF, ICC, comments or filenames from the source.
        clean = Image.new("RGBA", image.size)
        clean.paste(image)
        output = io.BytesIO()
        clean.save(output, format="PNG", optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        if len(encoded) < MAX_ENCODED_IMAGE:
            break
        image.thumbnail((max(1, image.width // 2), max(1, image.height // 2)))
    return {
        "image": encoded,
        "dimensions": list(image.size),
        "source_dimensions": list(original),
        "crop": crop,
    }


def main() -> None:
    """Return only a bounded encoder result; failures contain no asset paths."""
    try:
        job = json.loads(sys.stdin.buffer.read(16384))
        result = preview(job)
        sys.stdout.buffer.write(json.dumps(result).encode())
    except Exception:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
