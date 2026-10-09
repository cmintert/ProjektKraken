"""Verify that local push and release gates retain their critical checks."""

import pytest

from scripts.preflight import make_steps

pytestmark = pytest.mark.ci_fast


def test_push_runs_deep_quality_and_curated_regressions() -> None:
    """Every normal push must verify more than the remote smoke suite."""
    commands = [" ".join(command) for _, command in make_steps("push", "base123")]
    assert len(commands) == 9
    assert any("smoke or ci_fast" in value for value in commands)
    assert any("scripts.check_test_policy" in value for value in commands)
    assert any("scripts.check_complexity_policy --base-ref base123" in value for value in commands)
    assert any("scripts.check_visual_policy --base-ref base123" in value for value in commands)
    assert any("mypy src" in value for value in commands)
    assert any("sphinx-build -n -W" in value for value in commands)
    assert all("--update" not in value for value in commands)


def test_release_checks_entire_suite_without_double_fast_run() -> None:
    """A release candidate requires the full tests and coverage."""
    commands = [" ".join(command) for _, command in make_steps("release", "base123")]
    assert len(commands) == 9
    assert any("--cov=src" in value for value in commands)
    assert all("smoke or ci_fast" not in value for value in commands)
