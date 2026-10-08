"""Required theme-owned visual roles and accessible contrast validation."""

import re
from collections.abc import Mapping

TEXT_CONTRAST = 4.5
CONTROL_CONTRAST = 3.0
SRGB_LINEAR_THRESHOLD = 0.04045

CONTROL_ROLES = ("primary", "secondary", "quiet", "destructive")
CONTROL_STATES = ("normal", "hover", "pressed", "checked", "disabled")
SEMANTIC_ROLES = (
    "app_bg",
    "surface",
    "text_main",
    "entity_main",
    "event_main",
    "timeline_viewed_time",
    "timeline_world_time",
    "timeline_grid",
    "error",
    "warning",
    "success",
    "link_entity",
    "link_event",
    "link_unresolved",
    "link_neutral",
    "mode_bg",
    "mode_border",
    "mode_text",
    "focus_ring",
    "selection_bg",
    "selection_text",
    "supporting_text",
    "supporting_caption",
)
REQUIRED_VISUAL_ROLES = SEMANTIC_ROLES + tuple(
    f"action_{role}_{state}_{part}"
    for role in CONTROL_ROLES
    for state in CONTROL_STATES
    for part in ("bg", "text", "border")
)


def luminance(color: str) -> float:
    """Return WCAG relative luminance of an opaque six-digit theme color."""
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= SRGB_LINEAR_THRESHOLD else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first: str, second: str) -> float:
    """Return WCAG contrast ratio between two theme tokens."""
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def validate_visual_roles(name: str, theme: Mapping[str, str]) -> None:
    """Reject incomplete or invalid mappings with the theme and role names."""
    missing = sorted(set(REQUIRED_VISUAL_ROLES).difference(theme))
    invalid = [
        key
        for key in REQUIRED_VISUAL_ROLES
        if key in theme
        and not (
            re.fullmatch(r"#[0-9a-fA-F]{6}", theme[key])
            or (
                key.startswith("action_")
                and key.endswith(("_bg", "_border"))
                and theme[key] == "transparent"
            )
        )
    ]
    if missing or invalid:
        raise ValueError(
            f"Theme {name}: missing visual roles {missing}; invalid colors {invalid}"
        )


def contrast_failures(theme: Mapping[str, str]) -> list[str]:
    """Describe failures for the backgrounds used by the shared authoring UI."""
    failures = []
    for background in ("app_bg", "surface"):
        for foreground in (
            "link_entity",
            "link_event",
            "link_unresolved",
            "link_neutral",
            "supporting_text",
            "supporting_caption",
        ):
            if contrast(theme[foreground], theme[background]) < TEXT_CONTRAST:
                failures.append(f"{foreground}/{background}: text contrast < 4.5")
        if contrast(theme["focus_ring"], theme[background]) < CONTROL_CONTRAST:
            failures.append(f"focus_ring/{background}: contrast < 3")
    for role in CONTROL_ROLES:
        for state in CONTROL_STATES:
            prefix = f"action_{role}_{state}"
            bg = theme[f"{prefix}_bg"]
            backgrounds = (
                (theme["app_bg"], theme["surface"]) if bg == "transparent" else (bg,)
            )
            for background in backgrounds:
                if contrast(theme[f"{prefix}_text"], background) < TEXT_CONTRAST:
                    failures.append(f"{prefix}: text contrast < 4.5")
            if state != "disabled" and role != "quiet":
                for background in (theme["app_bg"], theme["surface"]):
                    if (
                        contrast(theme[f"{prefix}_border"], background)
                        < CONTROL_CONTRAST
                    ):
                        failures.append(f"{prefix}: boundary contrast < 3")
    for fg, bg, minimum in (
        ("timeline_viewed_time", "app_bg", 3),
        ("timeline_world_time", "app_bg", 3),
        ("mode_text", "mode_bg", 4.5),
        ("mode_border", "mode_bg", 3),
        ("selection_text", "selection_bg", 4.5),
    ):
        if contrast(theme[fg], theme[bg]) < minimum:
            failures.append(f"{fg}/{bg}: contrast < {minimum}")
    return failures
