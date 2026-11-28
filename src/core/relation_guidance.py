"""Suggestions and nonblocking hints for a proposed relation."""

from collections.abc import Iterable

from src.core.lifecycle import CHARACTER_TRANSITIONS
from src.core.relation_vocabulary import Vocabulary, filter_labels

_KINDS = ("entity", "event")
_MISMATCH = 2


def _endpoint_rank(
    vocabulary: Vocabulary, key: str, source_kind: str, target_kind: str
) -> int:
    if source_kind not in _KINDS or target_kind not in _KINDS:
        return 1
    definition = vocabulary.get(key, {})
    preferences = (
        definition.get("preferred_source_kind"),
        definition.get("preferred_target_kind"),
    )
    if any(
        preferred in _KINDS and preferred != actual
        for preferred, actual in zip(
            preferences, (source_kind, target_kind), strict=True
        )
    ):
        return _MISMATCH
    return 0 if any(preferred in _KINDS for preferred in preferences) else 1


def type_suggestions(
    keys: Iterable[str], vocabulary: Vocabulary, source_kind: str, target_kind: str
) -> list[tuple[str, str]]:
    """Return exact keys and display captions ordered by endpoint preference."""
    labels = filter_labels(
        (key for key in {*keys, *vocabulary} if key and key != "mentions"),
        vocabulary,
    )
    return sorted(
        labels.items(),
        key=lambda item: (
            _endpoint_rank(vocabulary, item[0], source_kind, target_kind),
            item[0].casefold(),
            item[0],
        ),
    )


def relation_hint(
    key: str, vocabulary: Vocabulary, source_kind: str, target_kind: str
) -> str:
    """Describe endpoint preferences and recognized lifecycle behavior."""
    hints = []
    if _endpoint_rank(vocabulary, key, source_kind, target_kind) == _MISMATCH:
        definition = vocabulary[key]
        source = definition.get("preferred_source_kind", "")
        target = definition.get("preferred_target_kind", "")
        if source in _KINDS and target in _KINDS:
            hints.append(
                f"This type usually connects {source.title()} → {target.title()}."
            )
        elif source in _KINDS:
            hints.append(f"This type usually starts from an {source.title()}.")
        else:
            hints.append(f"This type usually points to an {target.title()}.")
    lifecycle = key.strip().casefold()
    if lifecycle in CHARACTER_TRANSITIONS:
        hints.append(
            f"Kraken uses {lifecycle} relations with date evidence to assess "
            "a character’s lifecycle."
        )
    return "\n".join(hints)
