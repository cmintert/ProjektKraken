"""Theme and presentation policy contracts, independent of incidental pixels."""

import json
from pathlib import Path

import pytest

from scripts.check_visual_policy import (
    baseline_failures,
    check,
    scan_source,
    scan_stylesheet,
)
from src.core.theme_defaults import DEFAULT_THEMES
from src.core.visual_roles import contrast_failures, validate_visual_roles
from src.gui.widgets.wiki_link_presentation import resolve_link_presentation

pytestmark = pytest.mark.ci_fast
THEMES = json.loads(Path("themes.json").read_text())


@pytest.mark.parametrize("name", list(THEMES))
def test_complete_accessible_palettes(name):
    validate_visual_roles(name, THEMES[name])
    assert contrast_failures(THEMES[name]) == []
    assert THEMES[name]["link_entity"] != THEMES[name]["link_event"]
    assert THEMES[name]["link_unresolved"] not in (
        THEMES[name]["link_entity"],
        THEMES[name]["link_event"],
    )


def test_recovery_themes_match_bundled_roles():
    for name, theme in DEFAULT_THEMES.items():
        validate_visual_roles(name, theme)
        assert theme == THEMES[name]


def test_missing_and_invalid_tokens_fail_explicitly():
    theme = dict(THEMES["dark_mode"])
    del theme["mode_border"]
    theme["link_entity"] = "nonsense"
    with pytest.raises(ValueError, match="mode_border.*link_entity"):
        validate_visual_roles("incomplete", theme)


@pytest.mark.parametrize(
    "target,role,resolved",
    [
        ("id:ENT", "link_entity", True),
        ("Event", "link_event", True),
        ("shared", "link_unresolved", False),
        ("missing", "link_unresolved", False),
        ("id:Event", "link_unresolved", False),
    ],
)
def test_typed_and_unresolved_snapshot_resolution(target, role, resolved):
    items = [
        ("ent", "Entity", "entity"),
        ("evt", "Event", "event"),
        ("a", "Shared", "entity"),
        ("b", "Shared", "event"),
    ]
    state = resolve_link_presentation(
        target, items, {row[1].casefold() for row in items}
    )
    assert (state.role, state.resolved) == (role, resolved)
    assert state.tooltip


def test_loading_legacy_and_external_links_are_neutral():
    assert resolve_link_presentation("anything", [], None).role == "link_neutral"
    assert resolve_link_presentation("legacy", [], {"legacy"}).role == "link_neutral"
    assert resolve_link_presentation("https://example.com", [], set()).resolved


def test_policy_detects_literals_derivation_and_ignores_docs_and_tokens():
    source = '''"""Example #ffffff, not presentation."""
color = theme["link_entity"]
widget.setStyleSheet("color: #ffffff;")
brush = QColor(12, 24, 36)
named = QColor("red")
variant = QColor(color).lighter(120)
'''
    violations = scan_source(source, "src/gui/example.py")
    assert len(violations) == 4
    assert {v.rule for v in violations} == {"literal-color", "local-color-derivation"}


def test_reviewed_authored_colors_and_baseline_growth_removal():
    source = 'DEFAULT_MAP_COLOR = "#123456"'
    violations = scan_source(source, "src/gui/map.py")
    baseline = {
        "schema": 1,
        "exceptions": [
            {
                "key": violations[0].key,
                "count": 1,
                "reason": "Authored map data default, not UI chrome.",
            }
        ],
    }
    assert baseline_failures(violations, baseline) == []
    assert baseline_failures(violations * 2, baseline)
    assert baseline_failures([], baseline)
    assert baseline_failures(
        scan_source(source.replace("123456", "654321"), "src/gui/map.py"), baseline
    )
    baseline["exceptions"][0]["reason"] = ""
    assert baseline_failures(violations, baseline)


def test_repository_visual_policy():
    assert check() == []


def test_qss_templates_do_not_hide_literal_colors():
    source = "/* color: red; */\nQWidget {{ background: {surface};\ncolor: black; }}"
    violations = scan_stylesheet(source, "src/resources/example.qss")
    assert len(violations) == 1
    assert violations[0].line == 3
    assert not scan_stylesheet("QWidget {{ color: {text_main}; }}", "theme.qss")


def test_next_touch_retires_legacy_but_preserves_authored_data():
    from scripts.check_visual_policy import legacy_touch_failures, source_scopes

    before = 'def style():\n    color = "#123456"\n    return color\n'
    after = before.replace("return color", "return color.strip()")
    violations = scan_source(after, "src/gui/example.py")
    baseline = {"exceptions": [{"key": violations[0].key, "category": "legacy"}]}
    assert (
        baseline_failures(
            violations,
            {
                "schema": 1,
                "exceptions": [
                    {
                        **baseline["exceptions"][0],
                        "count": 1,
                        "reason": "KRT-54 existing debt",
                    }
                ],
            },
        )
        == []
    )
    assert source_scopes(before)["style"] != source_scopes(after)["style"]
    assert legacy_touch_failures(
        violations, baseline, {("src/gui/example.py", "style")}
    )
    assert not legacy_touch_failures(
        violations, baseline, {("src/gui/example.py", "other")}
    )
    baseline["exceptions"][0]["category"] = "authored-data"
    assert not legacy_touch_failures(
        violations, baseline, {("src/gui/example.py", "style")}
    )
    assert source_scopes(before) == source_scopes("\n" + before)
