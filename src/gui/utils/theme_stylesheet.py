"""Compile the controlled application QSS into fixed metrics and theme colors."""

import re
import string
from dataclasses import dataclass

_COLORS = frozenset(
    {
        "color",
        "background",
        "background-color",
        "border-color",
        "outline-color",
        "selection-color",
        "selection-background-color",
        "alternate-background-color",
        "gridline-color",
    }
)
_BORDERS = frozenset(
    {"border", "border-top", "border-bottom", "border-left", "border-right"}
)
_TOKEN_PREFIX = "__kraken_token_"


def _declarations(body: str) -> list[tuple[str, str]]:
    """Split authored declarations without splitting quoted URLs/functions."""
    pieces: list[str] = []
    start, depth, quote = 0, 0, ""
    for index, character in enumerate(body):
        if quote:
            if character == quote and (index == 0 or body[index - 1] != "\\"):
                quote = ""
        elif character in ("'", '"'):
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == ";" and depth == 0:
            pieces.append(body[start:index])
            start = index + 1
    pieces.append(body[start:])
    if quote or depth:
        raise ValueError("Unbalanced application QSS declaration")
    result = []
    for piece in pieces:
        if piece.strip():
            key, separator, value = piece.partition(":")
            if not separator:
                raise ValueError("Invalid application QSS declaration")
            result.append((key.strip(), value.strip()))
    return result


@dataclass(frozen=True)
class ThemeStylePack:
    """Fixed application metrics and ordered, theme-owned presentation rules."""

    metrics: str
    colors: tuple[tuple[str, str], ...]
    fields: tuple[str, ...]

    def render(
        self,
        theme: dict[str, str],
        *,
        shell: bool = False,
        prefixes: tuple[str, ...] = (),
    ) -> str:
        """Render colors; shell scopes own only the main-window chrome."""
        rules = []
        for selector, declarations in self.colors:
            parts = [part.strip() for part in selector.split(",")]
            if parts == ["QWidget"]:
                # The application palette owns ordinary inherited text. Repeating
                # this broad rule in every scope causes nested palette cascades.
                continue
            if shell:
                parts = [part for part in parts if part.startswith("QMainWindow")]
            if prefixes:
                parts = [part for part in parts if part.startswith(prefixes)]
            if parts:
                rules.append(", ".join(parts) + " { " + declarations + " }")
        result = "\n".join(rules)
        for field in self.fields:
            result = result.replace(_TOKEN_PREFIX + field + "__", theme[field])
        return result


def compile_theme_stylesheet(template: str) -> ThemeStylePack:
    """Compile the repository-owned, non-nested QSS grammar; fail on unknown tokens."""
    fields = tuple(
        sorted(
            {field for _, field, _, _ in string.Formatter().parse(template) if field}
        )
    )
    source = template.format(
        **{field: _TOKEN_PREFIX + field + "__" for field in fields}
    )
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    metrics, colors = [], []
    end = 0
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source):
        if source[end : match.start()].strip():
            raise ValueError("Unsupported application QSS rule")
        selector, body = match.group(1).strip(), match.group(2)
        fixed, dynamic = [], []
        for key, value in _declarations(body):
            if (
                key in _COLORS
                or key.endswith("-color")
                or (key.startswith("font-") and _TOKEN_PREFIX in value)
            ):
                dynamic.append(f"{key}: {value};")
            elif key in _BORDERS and _TOKEN_PREFIX in value:
                prefix, separator, token = value.rpartition(" ")
                if not separator or not token.startswith(_TOKEN_PREFIX):
                    raise ValueError("Unsupported themed QSS border shorthand")
                fixed.append(f"{key}: {prefix} transparent;")
                dynamic.append(f"{key}-color: {token};")
            else:
                if _TOKEN_PREFIX in value:
                    raise ValueError(f"Unclassified theme dependency: {key}")
                fixed.append(f"{key}: {value};")
        if fixed:
            metrics.append(selector + " { " + " ".join(fixed) + " }")
        if dynamic:
            colors.append((selector, " ".join(dynamic)))
        end = match.end()
    if source[end:].strip():
        raise ValueError("Unbalanced application QSS rule")
    return ThemeStylePack("\n".join(metrics), tuple(colors), fields)
