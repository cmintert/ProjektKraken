"""Tests for release-status tag classification."""

from unittest.mock import patch

import pytest

from scripts import check_release_status


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("0.19.0", "Released"),
        ("v0.19.0", "Released"),
        ("0.19.0-beta1", "Beta Package Release"),
        ("v0.19.0-beta2", "Beta Package Release"),
    ],
)
def test_release_status_recognizes_supported_tags(
    tag: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch.object(check_release_status, "get_pyproject_version", return_value="0.19.0"),
        patch.object(check_release_status, "get_runtime_version", return_value="0.19.0"),
        patch.object(
            check_release_status,
            "check_changelog",
            return_value={"has_unreleased": True, "has_current_version": True},
        ),
        patch.object(
            check_release_status,
            "check_git_status",
            return_value={"clean": True, "tag": tag},
        ),
        pytest.raises(SystemExit) as exit_info,
    ):
        check_release_status.main()

    assert exit_info.value.code == 0
    assert expected in capsys.readouterr().out
