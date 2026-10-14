"""Deterministic, offline search over immutable canonical Help sections."""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass

from src.core.help_bundle import HelpSearchDocument

_QUESTION_WORDS = frozenset(
    "a an and are at be by can change do does find for from have how i in is it "
    "of on or the to was what when where which why with".split()
)
_MIN_PREFIX_LENGTH = 3


def _words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def _matches(query: str, words: tuple[str, ...]) -> bool:
    index = bisect_left(words, query)
    return index < len(words) and (
        words[index] == query
        or len(query) >= _MIN_PREFIX_LENGTH
        and words[index].startswith(query)
    )


@dataclass(frozen=True)
class HelpSearchResult:
    """A validated section destination and plain-text presentation snapshot."""

    page: str
    fragment: str
    title: str
    snippet: str
    topic_ids: tuple[str, ...]


class HelpSearchService:
    """Rank canonical text without Qt, query persistence or external services."""

    def __init__(self, documents: tuple[HelpSearchDocument, ...]) -> None:
        """Index only snapshots supplied by the validated bundle reader."""
        self._documents = tuple(
            (
                document,
                tuple(sorted(set(_words(document.title)))),
                tuple(sorted(set(_words(document.text)))),
                tuple(sorted(set(_words(document.title) + _words(document.text)))),
                " ".join(_words(document.title)),
            )
            for document in documents
        )

    def search(self, query: str, limit: int = 50) -> tuple[HelpSearchResult, ...]:
        """Rank meaningful coverage, title phrase/title matches and body matches."""
        tokens = tuple(
            dict.fromkeys(w for w in _words(query) if w not in _QUESTION_WORDS)
        )
        meaningful = tuple(w for w in tokens if not w.isdecimal())
        numbers = tuple(w for w in tokens if w.isdecimal())
        required = meaningful or numbers
        if not required:
            return ()
        phrase = " ".join(meaningful)
        ranked = []
        if limit <= 0:
            return ()
        for document, title, body, combined, title_phrase in self._documents:
            coverage = sum(_matches(token, combined) for token in required)
            if not coverage:
                continue
            score = (
                coverage,
                int(bool(phrase) and phrase in title_phrase),
                sum(_matches(token, title) for token in required),
                sum(_matches(token, body) for token in required),
                sum(_matches(token, combined) for token in numbers),
            )
            ranked.append((score, document))
        ranked.sort(
            key=lambda entry: (
                tuple(-part for part in entry[0]),
                entry[1].page,
                entry[1].fragment,
            )
        )
        results = []
        destinations: set[tuple[str, str]] = set()
        for _score, document in ranked:
            destination = (document.page, document.fragment)
            if destination in destinations:
                continue
            destinations.add(destination)
            results.append(
                HelpSearchResult(
                    document.page,
                    document.fragment,
                    document.title,
                    self._snippet(document.text, required),
                    document.topic_ids,
                )
            )
            if len(results) >= max(1, min(limit, 50)):
                break
        return tuple(results)

    @staticmethod
    def _snippet(text: str, tokens: tuple[str, ...]) -> str:
        text = " ".join(text.split())
        normalized = unicodedata.normalize("NFKC", text).casefold()
        positions = [normalized.find(token) for token in tokens if token in normalized]
        start = max(0, min(positions, default=0) - 40)
        if start:
            boundary = text.find(" ", start)
            start = boundary + 1 if boundary >= 0 else start
        prefix = "…" if start else ""
        body = text[start : start + 180 - len(prefix)]
        if start + len(body) < len(text):
            body = body[: 177 - len(prefix)].rsplit(" ", 1)[0] + "…"
        return prefix + body
