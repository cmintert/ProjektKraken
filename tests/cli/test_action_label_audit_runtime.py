"""Local audit profiles and resource guards remain small and fail closed."""

import json

import pytest

from scripts.action_label_audit_runtime import audit_slot, write_streamed_report
from scripts.check_action_labels import main

pytestmark = pytest.mark.ci_fast


def test_concurrent_audit_is_rejected_and_slot_is_reusable(tmp_path):
    lock = tmp_path / "audit.lock"
    with audit_slot(lock):
        with pytest.raises(OSError):
            with audit_slot(lock):
                pytest.fail("Overlapping audit acquired the same slot")
    with audit_slot(lock):
        assert lock.exists()


@pytest.mark.parametrize("metadata", [{}, {"matrix": "full"}])
def test_streamed_report_preserves_all_snapshots_and_failures(tmp_path, metadata):
    records = [
        {"surface": "A", "controls": [{"text": "Apply"}], "failures": []},
        {"surface": "B", "failures": [{"kind": "vertical_clipping"}]},
    ]
    source = tmp_path / "records.jsonl"
    source.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    output = tmp_path / "report.json"
    assert write_streamed_report(output, metadata, source) == (2, 1)
    assert json.loads(output.read_text("utf-8")) == {
        **metadata,
        "records": records,
    }


def test_malformed_stream_cannot_produce_successful_report(tmp_path):
    source = tmp_path / "records.jsonl"
    source.write_text("invalid json\n", encoding="utf-8")
    with pytest.raises(ValueError):
        write_streamed_report(tmp_path / "report.json", {}, source)


def test_default_profile_is_quick_and_full_is_explicit(tmp_path, monkeypatch):
    from scripts import check_action_labels

    profiles = []
    monkeypatch.setattr(check_action_labels, "ROOT", tmp_path)
    monkeypatch.setattr(
        check_action_labels,
        "_run_parent",
        lambda args: profiles.append(args.matrix) or 0,
    )
    assert main(["--report-dir", str(tmp_path)]) == 0
    assert main(["--matrix", "full", "--report-dir", str(tmp_path)]) == 0
    assert profiles == ["quick", "full"]
