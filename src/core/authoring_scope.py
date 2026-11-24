"""World-specific visibility and creation defaults for scoped authoring."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

ScopeMode = Literal["any", "all"]


def _tags(values: object) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    return tuple(
        dict.fromkeys(
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        )
    )


@dataclass(frozen=True)
class AuthoringScope:
    """A tag expression and its explicit defaults for new content."""

    tags: tuple[str, ...] = ()
    mode: ScopeMode = "any"
    creation_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require an explicit subset for an ambiguous ANY expression."""
        if self.mode not in {"any", "all"}:
            raise ValueError("Choose ANY or ALL.")
        tags = _tags(self.tags)
        defaults = _tags(self.creation_tags)
        if self.mode == "all" or len(tags) <= 1:
            defaults = tags
        elif not defaults or not set(defaults).issubset(tags):
            raise ValueError("Choose one or more creation tags from this ANY scope.")
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "creation_tags", defaults)

    def matches(self, tags: Iterable[str]) -> bool:
        """Test canonical tag names, including their authored case."""
        if not self.tags:
            return True
        membership = set(tags)
        if self.mode == "all":
            return membership.issuperset(self.tags)
        return not membership.isdisjoint(self.tags)

    def to_dict(self) -> dict[str, object]:
        """Return an isolated settings or worker payload."""
        return {
            "tags": list(self.tags),
            "mode": self.mode,
            "creation_tags": list(self.creation_tags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "AuthoringScope":
        """Load a saved scope or a queued request."""
        mode: ScopeMode = "all" if data.get("mode") == "all" else "any"
        return cls(_tags(data.get("tags")), mode, _tags(data.get("creation_tags")))
