"""Decide when Markdown must stay in exact, editable source form."""

import re

_BLOCK_CONSTRUCT = re.compile(
    r"(?m)^(?:[ \t]{4,}|[ \t]{0,3}(?:[-+*] |\d+[.)] |> |```|~~~|"
    r"#{4,6} |\| |: |(?:---|\*\*\*|___)\s*$))"
)
_RICH_INLINE_CONSTRUCT = re.compile(
    r"`|\\[\\`*_{}\[\]()#+.!<>-]|!?\[[^\]\n]+\]\([^\n)]*\)|"
    r"\[[^\]\n]+\]\[[^\]\n]*\]|<[/!A-Za-z][^>]*>|~~|__|"
    r"(?<!\w)_[^_\n]+_(?!\w)"
)


def requires_source_mode(source: str) -> bool:
    """Keep constructs outside the rich serializer's vocabulary verbatim."""
    return bool(
        _BLOCK_CONSTRUCT.search(source)
        or _RICH_INLINE_CONSTRUCT.search(source)
        or re.search(r"(?m)^.+\|.+\n[ \t]*\|?[ \t]*:?-{3,}", source)
    )
