"""Frozen preview equivalence, source-change guards and safe worker preparation."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QThread

from src.core.ai_generation import GenerationRequest, PreparedGeneration
from src.core.authoring_context import EntityAuthoringContext
from src.gui.dialogs.prepared_generation_dialog import PreparedGenerationDialog
from src.gui.widgets.llm_generation_widget import GenerationWorker, LLMGenerationWidget

pytestmark = pytest.mark.ci_fast


def test_prepared_prompt_is_sent_without_retrieval_or_context_lookups(qapp):
    prepared = PreparedGeneration(
        {"system": "System", "user": "Frozen exact context"},
        "World facts",
        "Retrieved text",
        "Map facts",
        (135.0,),
    )
    request = GenerationRequest(
        {"system": "changed", "user": "changed"},
        prepared=prepared,
        authoring_context_enabled=True,
        rag_enabled=True,
        entity_context_mode="at_playhead",
        authoring_date=135.0,
    )
    worker = GenerationWorker(MagicMock(), "ignored", 100, 0.1, request=request)
    with (
        patch.object(worker, "_apply_authoring_context_to_prompt") as lookup,
        patch.object(worker, "_apply_rag_to_prompt") as rag,
        patch.object(worker, "_apply_spatial_to_prompt") as spatial,
    ):
        worker.prepare_context()
    lookup.assert_not_called()
    rag.assert_not_called()
    spatial.assert_not_called()
    assert worker.prompt == prepared.prompt
    assert worker.authoring_context_used == "World facts"
    assert worker.description_date_values == (135.0,)
    assert request.to_dict()["prepared"]["prompt"] == prepared.prompt


def test_preparation_runs_off_gui_thread_and_never_calls_provider(qtbot):
    request = GenerationRequest(
        {"system": "", "user": "{{AUTHORING_CONTEXT}}"},
        db_path="unused",
        target_id="person",
        object_type="entity",
        authoring_context_enabled=True,
        entity_context_mode="at_playhead",
        authoring_date=0.0,
        rag_enabled=False,
    )
    threads = []

    def lookup(*_args, **_kwargs):
        threads.append(QThread.currentThread())
        return EntityAuthoringContext("person", context_date=0.0, mode="at_playhead")

    provider = MagicMock()
    worker = GenerationWorker(
        provider, "ignored", 100, 0.1, request=request, preview_only=True
    )
    try:
        with patch(
            "src.gui.widgets.llm_generation_widget.lookup_entity_authoring_context",
            side_effect=lookup,
        ):
            with qtbot.waitSignal(worker.context_prepared) as result:
                worker.start()
            assert worker.wait(5000)
        assert threads and threads[0] is not QThread.currentThread()
        assert isinstance(result.args[0], dict)
        prepared = PreparedGeneration.from_dict(result.args[0])
        assert "Authoritative Context" in prepared.prompt["user"]
        provider.generate.assert_not_called()
        provider.metadata.assert_not_called()
    finally:
        worker.cancel()
        worker.wait()


def test_missing_temporal_context_cannot_silently_send_history(qapp):
    request = GenerationRequest(
        {"user": "{{AUTHORING_CONTEXT}}"},
        object_type="entity",
        authoring_context_enabled=True,
        entity_context_mode="at_playhead",
    )
    worker = GenerationWorker(MagicMock(), "ignored", 100, 0.1, request=request)
    with pytest.raises(ValueError, match="viewing date"):
        worker.prepare_context()


def test_preview_invalidation_retains_text_but_disables_send(qtbot):
    owner = LLMGenerationWidget()
    qtbot.addWidget(owner)
    dialog = PreparedGenerationDialog(owner)
    owner._preview_dialog = dialog
    dialog.present({"user": "Reviewed prompt"}, "Captured at 135")
    owner._prepared_request = GenerationRequest({"user": "Reviewed prompt"})
    owner.invalidate_context_preview()
    assert not dialog.generate_button.isEnabled()
    assert "Reviewed prompt" in dialog.text.toPlainText()
    assert owner._prepared_request is None
    owner._preview_dialog = None
    dialog.close()


def test_context_mode_availability_follows_world_context_toggle(qtbot):
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    widget._get_generation_context = MagicMock(return_value={"object_type": "entity"})
    widget.world_context_cb.setChecked(False)
    assert not widget.entity_context_mode.isEnabled()
    widget.world_context_cb.setChecked(True)
    assert widget.entity_context_mode.isEnabled()


def test_preview_generate_preserves_request_and_exact_messages(qtbot):
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    context = {
        "object_type": "entity",
        "object_id": "person",
        "existing_description": "Draft",
    }
    widget._get_generation_context = MagicMock(return_value=context)
    widget._resolve_db_path = MagicMock(return_value="world.kraken")
    request = GenerationRequest(
        {"user": "Original task"},
        db_path="world.kraken",
        target_id="person",
        object_type="entity",
        source_hash=widget._hash_source_description(context),
        prepared=PreparedGeneration({"user": "Task and reviewed facts"}),
    )
    widget._prepared_request = request
    dialog = PreparedGenerationDialog(widget)
    widget._preview_dialog = dialog
    with (
        patch("src.gui.widgets.llm_generation_widget.create_provider"),
        patch.object(widget, "_start_generation") as start,
    ):
        widget._generate_prepared_preview()
    assert start.call_args.kwargs["prepared_request"] is request
    widget._prepared_request = replace(request, source_hash="obsolete")
    with patch.object(widget, "_start_generation") as stale:
        widget._generate_prepared_preview()
    stale.assert_not_called()
    assert widget._prepared_request is None
    widget._preview_dialog = None
