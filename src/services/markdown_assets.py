"""Copy contained Markdown images into a staged publishing destination."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote

_IMAGE = re.compile(r"!\[([^\]]*)\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")
_EMBED = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def copy_markdown_images(
    text: str,
    world: Path | None,
    directory: Path,
    link_prefix: str,
    *,
    enabled: bool = True,
) -> str:
    """Publish local images with stable names; omit unavailable/disabled images."""
    root = world.resolve() if world is not None else None

    def image(source: str, label: str) -> str:
        if not enabled:
            return label
        path = (root / unquote(source.strip("<>"))).resolve() if root else None
        if (
            root is None
            or path is None
            or not path.is_relative_to(root)
            or not path.is_file()
        ):
            return f"[Image: {label or source}]"
        directory.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(path.read_bytes()).hexdigest() + path.suffix.lower()
        output = directory / name
        shutil.copyfile(path, output)
        return f"![{label}]({quote(link_prefix + '/' + name, safe='/')})"

    text = _IMAGE.sub(lambda match: image(match[2], match[1]), text)
    return _EMBED.sub(lambda match: image(match[1], Path(match[1]).stem), text)


def markdown_image_warnings(text: str, world: Path | None) -> list[str]:
    """Report unavailable inline images before the export is approved."""
    root = world.resolve() if world else None
    sources = [match[2] for match in _IMAGE.finditer(text)]
    sources.extend(match[1] for match in _EMBED.finditer(text))
    warnings = []
    for source in sources:
        path = (root / unquote(source.strip("<>"))).resolve() if root else None
        if (
            root is None
            or path is None
            or not path.is_relative_to(root)
            or not path.is_file()
        ):
            warnings.append(f"Image omitted: {source} (missing or outside the world).")
    return warnings
