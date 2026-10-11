"""Native review evidence cannot be replaced by a simulated or stale record."""

import json
from types import SimpleNamespace

import pytest

from scripts.action_label_review import native_review_failures

pytestmark = pytest.mark.ci_fast


def test_missing_and_pending_native_review_block_release(tmp_path):
    manifest = tmp_path / "native-review.json"
    assert native_review_failures(manifest, tmp_path, [])
    manifest.write_text(json.dumps({"status": "pending"}), encoding="utf-8")
    assert (
        "pending"
        in native_review_failures(manifest, tmp_path, [SimpleNamespace(key="Audit")])[0]
    )


def test_stale_native_review_cannot_approve_changed_presentation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.action_label_review.presentation_fingerprint", lambda root: "current"
    )
    manifest = tmp_path / "native-review.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "approved",
                "reviewer": "Fixture reviewer",
                "reviewed_at": "2026-10-11",
                "presentation_fingerprint": "old",
                "records": [],
            }
        ),
        encoding="utf-8",
    )
    assert (
        "does not match"
        in native_review_failures(manifest, tmp_path, [SimpleNamespace(key="Audit")])[0]
    )


def test_current_header_without_native_surface_records_is_incomplete(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "scripts.action_label_review.presentation_fingerprint", lambda root: "current"
    )
    manifest = tmp_path / "native-review.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "approved",
                "reviewer": "Fixture reviewer",
                "reviewed_at": "2026-10-11",
                "presentation_fingerprint": "current",
                "records": [],
            }
        ),
        encoding="utf-8",
    )
    failures = native_review_failures(
        manifest, tmp_path, [SimpleNamespace(key="Audit")]
    )
    assert len(failures) == 4
    assert any("1.25" in failure for failure in failures)
