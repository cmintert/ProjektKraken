"""Exercise frozen Markdown rules and their distributed licence notices."""

from pathlib import Path

from src.core.markdown_content import (
    PROFILE_VERSION,
    RenderTarget,
    parse_content,
    render_content,
)

MARKDOWN_NOTICES = ("markdown-it-py", "mdurl", "linkify-it-py", "mdit-py-plugins")


def probe_markdown(notice_directory: Path | None = None) -> dict[str, object]:
    """Fail when a frozen parser, plugin, linkifier or notice is missing."""
    source = (
        "| A | B |\n| - | - |\n| [[id:probe|Label]] | ~~old~~ |\n\n"
        "HTML https://example.org\nnext[^n]\n\n"
        "*[HTML]: Hypertext\n\nTerm\n: Definition\n\n[^n]: Note"
    )
    rendered = render_content(parse_content(source), RenderTarget.PUBLISHED)
    required = (
        "<table>",
        "<s>old</s>",
        'data-target="id:probe"',
        'href="https://example.org"',
        "<abbr",
        "<dl>",
        'id="fn1"',
    )
    if not all(fragment in rendered for fragment in required):
        raise ValueError(
            "Packaged Markdown profile did not render its required features"
        )
    notices = []
    if notice_directory is not None:
        for name in MARKDOWN_NOTICES:
            path = notice_directory / f"{name}.txt"
            if "Permission is hereby granted" not in path.read_text(encoding="utf-8"):
                raise ValueError(f"Packaged licence notice is incomplete: {name}")
            notices.append(path.name)
    return {
        "profile_version": PROFILE_VERSION,
        "features_checked": list(required),
        "licence_files": notices,
    }
