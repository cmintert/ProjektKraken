"""Snapshot-only wiki-link presentation, independent of navigation and storage."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


@dataclass(frozen=True)
class LinkPresentation:
    """Meaning and non-color explanation for an inline link."""

    role: str
    tooltip: str
    resolved: bool

    @property
    def underline(self) -> QTextCharFormat.UnderlineStyle:
        """Use a dotted cue for unresolved links without an alarm treatment."""
        return (
            QTextCharFormat.UnderlineStyle.SingleUnderline
            if self.resolved
            else QTextCharFormat.UnderlineStyle.DotLine
        )


def resolve_link_presentation(
    target: str,
    items: list[tuple[str, str, str]],
    names: set[str] | None,
) -> LinkPresentation:
    """Resolve display meaning from completion snapshots, never from a database.

    None names means targets have not loaded. ID targets never fall through to
    a same-named entry. Ambiguous names do not pretend to identify one object.
    """
    if "://" in target or target.startswith(("mailto:", "#")):
        return LinkPresentation("link_neutral", "Open external link", True)
    if names is None:
        return LinkPresentation("link_neutral", "Link target information loading", True)
    id_based = target.casefold().startswith("id:")
    key = target[3:] if id_based else target
    matches = [
        (name, kind)
        for item_id, name, kind in items
        if item_id.casefold() == key.casefold()
        or (not id_based and name.casefold() == key.casefold())
    ]
    if len(matches) == 1:
        name, kind = matches[0]
        if kind in ("entity", "event"):
            return LinkPresentation(f"link_{kind}", f"{kind.title()}: {name}", True)
        return LinkPresentation("link_neutral", f"Entry: {name}", True)
    if len(matches) > 1:
        return LinkPresentation(
            "link_unresolved", "Unresolved link: multiple entries match", False
        )
    if not id_based and key.casefold() in names:
        return LinkPresentation("link_neutral", f"Entry: {key}", True)
    return LinkPresentation(
        "link_unresolved", "Unresolved link: target not found", False
    )


class WikiPresentationHighlighter(QSyntaxHighlighter):
    """Apply theme colors without editing text, metadata or document undo history."""

    def __init__(
        self,
        document: QTextDocument,
        presentation: Callable[[str], LinkPresentation],
        theme: Mapping[str, str],
    ) -> None:
        """Compose the existing GUI snapshot resolver and active theme."""
        super().__init__(document)
        self.presentation = presentation
        self.theme = theme
        self.rich = True

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        """Paint foreground and link cues as transient layout formats."""
        if not self.rich:
            return
        base = QTextCharFormat()
        base.setForeground(QColor(self.theme["text_main"]))
        self.setFormat(0, len(text), base)
        block = self.currentBlock()
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isAnchor():
                state = self.presentation(fragment.charFormat().anchorHref())
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(self.theme[state.role]))
                fmt.setUnderlineColor(QColor(self.theme[state.role]))
                fmt.setUnderlineStyle(state.underline)
                self.setFormat(
                    fragment.position() - block.position(), fragment.length(), fmt
                )
            iterator += 1
