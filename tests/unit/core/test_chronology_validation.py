"""World chronology feasibility without invented calendar precision."""

import pytest

from src.core.calendar import CalendarConfig, MonthDefinition, WeekDefinition
from src.core.date_parser import DateParser
from src.core.temporal_constraints import (
    TemporalConstraint,
    chronology_issues,
)
from src.core.temporal_constraints import (
    TemporalConstraintKind as Kind,
)

pytestmark = pytest.mark.ci_fast


def rule(a: str, relation: Kind, b: str, gap: float = 0) -> TemporalConstraint:
    return TemporalConstraint(a, relation, b, gap)


def test_inverse_duplicate_and_global_cycle() -> None:
    duplicate = chronology_issues(
        [rule("a", Kind.BEFORE, "b"), rule("b", Kind.AFTER, "a")]
    )
    assert any(issue.code == "duplicate" for issue in duplicate)
    cycle = chronology_issues(
        [
            rule("a", Kind.BEFORE, "b"),
            rule("b", Kind.BEFORE, "c"),
            rule("c", Kind.BEFORE, "a"),
        ]
    )
    assert any(issue.code == "cycle" for issue in cycle)


def test_shared_transition_requires_one_common_point() -> None:
    parser = DateParser(CalendarConfig.create_default())
    converter = parser.converter
    bounds = {
        name: parser.parse_expression(text).resolve_bounds(converter)
        for name, text in (
            ("a", "between 1200 and 1202"),
            ("b", "between 1201 and 1203"),
            ("c", "between 1203 and 1204"),
        )
    }
    issues = chronology_issues(
        [rule("a", Kind.SAME_AS, "b"), rule("b", Kind.SAME_AS, "c")],
        bounds,
    )
    assert any(issue.code == "shared_transition_conflict" for issue in issues)


def test_coarse_dates_allow_strict_order_within_same_period() -> None:
    parser = DateParser(CalendarConfig.create_default())
    converter = parser.converter
    for text in ("1210", "1 January 1210"):
        bound = parser.parse_expression(text).resolve_bounds(converter)
        assert not chronology_issues(
            [rule("a", Kind.BEFORE, "b")], {"a": bound, "b": bound}
        )


def test_legacy_exact_instant_cannot_precede_itself() -> None:
    from src.core.temporal_expression import ResolvedTemporalBounds

    exact = ResolvedTemporalBounds(42, 42)
    issues = chronology_issues([rule("a", Kind.BEFORE, "b")], {"a": exact, "b": exact})
    assert any(issue.code == "impossible_chain" for issue in issues)


def test_full_chain_and_gap_must_fit_bounds() -> None:
    from src.core.temporal_expression import ResolvedTemporalBounds

    bounds = {
        "a": ResolvedTemporalBounds(0, 10),
        "b": ResolvedTemporalBounds(0, 20),
        "c": ResolvedTemporalBounds(0, 11),
    }
    issues = chronology_issues(
        [rule("a", Kind.BEFORE, "b", 8), rule("b", Kind.BEFORE, "c", 4)],
        bounds,
    )
    assert any(issue.code == "impossible_chain" for issue in issues)


def test_approximate_dates_supply_no_hard_bound() -> None:
    parser = DateParser(CalendarConfig.create_default())
    converter = parser.converter
    approximate = parser.parse_expression("c. 1210").resolve_bounds(converter)
    assert approximate.hard_start is None
    assert not chronology_issues(
        [rule("a", Kind.BEFORE, "b")],
        {"a": approximate, "b": approximate},
    )


def test_custom_calendar_year_zero_and_pre_epoch() -> None:
    config = CalendarConfig(
        id="short-year",
        name="Short year",
        months=[
            MonthDefinition(name="First", abbreviation="F", days=10),
            MonthDefinition(name="Second", abbreviation="S", days=10),
        ],
        week=WeekDefinition(day_names=["A", "B"], day_abbreviations=["A", "B"]),
        year_variants=[],
        epoch_name="SE",
    )
    parser = DateParser(config)
    bounds = {
        year: parser.parse_expression(year).resolve_bounds(parser.converter)
        for year in ("-1", "0")
    }
    assert not chronology_issues([rule("-1", Kind.BEFORE, "0")], bounds)
    assert any(
        issue.code == "impossible_chain"
        for issue in chronology_issues([rule("0", Kind.BEFORE, "-1")], bounds)
    )


def test_one_sided_bounds_and_transitive_order() -> None:
    from src.core.temporal_expression import ResolvedTemporalBounds

    bounds = {
        "a": ResolvedTemporalBounds(None, 5),
        "b": ResolvedTemporalBounds(),
        "c": ResolvedTemporalBounds(6, None),
    }
    assert not chronology_issues(
        [rule("a", Kind.BEFORE, "b"), rule("b", Kind.BEFORE, "c")],
        bounds,
    )


def test_unavailable_self_duplicate_and_invalid_gap_are_reported() -> None:
    from src.core.temporal_expression import ResolvedTemporalBounds

    issues = chronology_issues(
        [
            rule("a", Kind.BEFORE, "a"),
            rule("a", Kind.SAME_AS, "missing", 1),
            rule("missing", Kind.SAME_AS, "a"),
        ],
        {"a": ResolvedTemporalBounds(0, 1)},
    )
    assert {"self_reference", "invalid_offset", "duplicate", "missing_anchor"} <= {
        issue.code for issue in issues
    }
