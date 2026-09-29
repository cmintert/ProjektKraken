"""Tests for source and packaged revision labels in the window title."""

import json
from unittest.mock import patch

from src.app.build_identity import get_commit_id, window_title


def test_development_title_includes_checkout_commit(tmp_path):
    with (
        patch("src.app.build_identity.sys.frozen", False, create=True),
        patch("src.app.build_identity.get_executable_dir", return_value=tmp_path),
        patch("src.app.build_identity.subprocess.run") as run,
    ):
        run.return_value.stdout = "ABCDEF123456\n"
        assert window_title("Project Kraken - v1 (Beta)", "My World") == (
            "Project Kraken - v1 (Beta) - abcdef12 - My World"
        )
        assert run.call_args.kwargs["cwd"] == tmp_path


def test_packaged_title_reads_build_metadata(tmp_path):
    (tmp_path / "build-info.json").write_text(
        json.dumps({"commit": "1234567890abcdef1234567890abcdef12345678"}),
        encoding="utf-8",
    )
    with (
        patch("src.app.build_identity.sys.frozen", True, create=True),
        patch("src.app.build_identity.get_executable_dir", return_value=tmp_path),
        patch("src.app.build_identity.subprocess.run") as run,
    ):
        assert get_commit_id() == "12345678"
        run.assert_not_called()


def test_title_omits_unavailable_or_invalid_commit(tmp_path):
    (tmp_path / "build-info.json").write_text(
        '{"commit": "not-a-commit"}', encoding="utf-8"
    )
    with (
        patch("src.app.build_identity.sys.frozen", True, create=True),
        patch("src.app.build_identity.get_executable_dir", return_value=tmp_path),
    ):
        assert window_title("Project Kraken - v1 (Beta)", "My World") == (
            "Project Kraken - v1 (Beta) - My World"
        )
