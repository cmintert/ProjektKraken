"""Exercise prompt invariants and session job ownership without real models."""

import json
from unittest.mock import patch

import pytest

from src.core.generation_experiment import render_variant
from src.core.mcp_access import McpFailure
from src.services.generation_experiments import GenerationExperiments

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def experiments(qapp):
    store = GenerationExperiments()
    yield store
    store.reset()
    store._pool.shutdown(wait=True)


def prepare(store):
    identifier, _ = store.reserve({"idempotency_key": "prepare"})
    store.entries[identifier].update(
        state="ready",
        baseline={"system": "policy", "user": "baseline"},
        blocks={"facts": "uncertain allegiance", "task": "describe"},
        snapshot_revision="original",
    )
    return identifier


def test_baseline_and_variant_preserve_exact_payloads():
    baseline = {"system": "application rule", "user": "exact baseline"}
    blocks = {"facts": "Unknown\n  Exact spacing", "task": "Describe"}
    assert render_variant(baseline, blocks, {}) == baseline
    rendered = render_variant(
        baseline,
        blocks,
        {
            "order": ["task", "facts"],
            "headings": {"facts": "Evidence"},
            "instruction": "Be concise",
        },
    )
    assert rendered["system"] == baseline["system"]
    assert blocks["facts"] in rendered["user"]
    assert rendered["user"].index("Describe") < rendered["user"].index("Unknown")


@pytest.mark.parametrize(
    "variant",
    [
        {"order": ["facts", "facts"]},
        {"order": []},
        {"system": "replace policy"},
        {"headings": {"unknown": "new fact"}},
    ],
)
def test_invalid_variant_rejected(variant):
    with pytest.raises(McpFailure):
        render_variant({"system": "rule"}, {"facts": "x", "task": "y"}, variant)


def test_prepare_retry_and_conflict(experiments):
    args = {"idempotency_key": "stable"}
    first, fresh = experiments.reserve(args)
    assert fresh
    assert experiments.reserve(args) == (first, False)
    with pytest.raises(McpFailure):
        experiments.reserve({**args, "task": "changed"})


def test_trial_retry_does_not_start_twice(experiments):
    identifier = prepare(experiments)
    args = {"idempotency_key": "trial"}
    with patch.object(experiments, "_launch") as launch:
        first = experiments.start(identifier, args)
        second = experiments.start(identifier, args)
    assert first["trial_id"] == second["trial_id"]
    assert launch.call_count == 1


def test_busy_is_enforced_without_run_quota(experiments):
    identifier = prepare(experiments)
    experiments._busy.set()
    with pytest.raises(McpFailure, match="BUSY"):
        experiments.start(identifier, {"idempotency_key": "busy"})
    experiments._busy.clear()
    with patch.object(experiments, "_launch"):
        for index in range(12):
            experiments.start(identifier, {"idempotency_key": f"trial-{index}"})
    assert len(experiments.entries[identifier]["trials"]) == 12


def test_more_than_three_experiments_are_retained(experiments):
    for index in range(5):
        identifier, _ = experiments.reserve({"idempotency_key": f"prepare-{index}"})
        experiments.entries[identifier]["state"] = "ready"
    assert len(experiments.entries) == 5


def test_prepare_requires_final_revision_verification(experiments):
    identifier, _ = experiments.reserve({"idempotency_key": "prepare"})
    experiments.entries[identifier]["snapshot_revision"] = "old"
    experiments._accept(
        (experiments.epoch, identifier, None, {"baseline": {}}, "", False)
    )
    assert experiments.entries[identifier]["state"] == "preparing"
    assert "_candidate" not in experiments.public(identifier)
    experiments.publish(identifier, "new")
    assert experiments.entries[identifier]["state"] == "failed"


def test_frozen_revision_reads_and_private_projection(experiments):
    identifier = prepare(experiments)
    experiments.entries[identifier]["settings"] = {"api_key": "secret"}
    page = experiments.call(
        "get_generation_experiment",
        {
            "experiment_id": identifier,
            "expected_revision": "original",
        },
    )
    assert "secret" not in page["content"]
    assert json.loads(page["content"])["snapshot_revision"] == "original"
    with pytest.raises(McpFailure, match="WORLD_CHANGED"):
        experiments.call(
            "get_generation_experiment",
            {
                "experiment_id": identifier,
                "expected_revision": "different",
            },
        )


def test_revocation_drops_late_result(experiments):
    identifier = prepare(experiments)
    epoch = experiments.epoch
    experiments.reset()
    experiments._accept((epoch, identifier, None, {"baseline": "private"}, "", False))
    assert not experiments.entries


def test_cancel_other_experiment_does_not_abort_active_worker(experiments):
    identifier = prepare(experiments)
    experiments._active_id = "other"
    with patch.object(experiments, "cancel_active") as cancel:
        experiments.call("cancel_generation_experiment", {"experiment_id": identifier})
    cancel.assert_not_called()


def test_shared_worker_runs_frozen_trial_without_lookups(experiments):
    from src.core.ai_generation import GenerationRequest, PreparedGeneration

    identifier = prepare(experiments)
    entry = experiments.entries[identifier]
    prompt = entry["baseline"]
    entry.update(
        prepared=PreparedGeneration(prompt).to_dict(),
        request=GenerationRequest(prompt).to_dict(),
        settings={
            "generate_url": "http://127.0.0.1:1234/v1/chat/completions",
            "embed_url": "http://127.0.0.1:1234/v1/embeddings",
        },
        filter_reasoning=True,
    )
    with patch("src.services.providers.lmstudio_provider.LMStudioProvider") as factory:
        provider = factory.return_value
        provider.metadata.return_value = {"supports_streaming": False}
        provider.generate.return_value = {
            "text": "Useful description",
            "model": "local-test",
            "usage": {},
        }
        with patch("src.services.generation_worker.RAGService") as retrieval:
            result = experiments._generate(entry, prompt)
    assert result["raw_text"] == "Useful description"
    assert result["presented_text"] == "Useful description"
    retrieval.assert_not_called()
    provider.generate.assert_called_once()
    transport = factory.call_args.kwargs["request_session"]
    assert transport.trust_env is False


def test_restricted_provider_disables_redirects():
    from unittest.mock import Mock

    from src.services.providers.lmstudio_provider import LMStudioProvider

    transport = Mock()
    provider = LMStudioProvider(model="local-test", request_session=transport)
    provider._post("http://127.0.0.1:1234", json={})
    transport.post.assert_called_once_with(
        "http://127.0.0.1:1234",
        allow_redirects=False,
        json={},
    )
