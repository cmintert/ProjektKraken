import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.ai_generation import (
    GenerationApplyMode,
    GenerationRequest,
    GenerationReviewResult,
    ModelReply,
    TaskIntent,
    TaskTemplate,
    TaskTemplateSource,
)

# Reload the widget module after QSettings is mocked to ensure it uses MockQSettings
if "src.gui.widgets.llm_generation_widget" in sys.modules:
    import src.gui.widgets.llm_generation_widget

    importlib.reload(src.gui.widgets.llm_generation_widget)

from src.gui.widgets.llm_generation_widget import GenerationWorker, LLMGenerationWidget


@patch(
    "src.gui.widgets.llm_generation_widget.format_event_authoring_context",
    return_value="[Authoritative Context]\nKnown fact",
)
@patch("src.gui.widgets.llm_generation_widget.lookup_event_authoring_context")
def test_generation_worker_injects_event_context_without_rag(
    lookup_context,
    _format_context,
) -> None:
    """World Context is independent of similarity retrieval."""
    lookup_context.return_value = MagicMock()
    request = GenerationRequest(
        prompt={
            "system": "System",
            "user": (
                "[Event]\nName: Eclipse\n\n{{AUTHORING_CONTEXT}}\n\n"
                "[Task]\nRevise"
            ),
        },
        max_tokens=100,
        temperature=0.7,
        db_path="world.kraken",
        target_id="event-id",
        object_type="event",
        authoring_context_enabled=True,
        authoring_date=42.0,
        rag_enabled=False,
    )
    worker = GenerationWorker(MagicMock(), request.prompt, 100, 0.7, request=request)

    worker._apply_authoring_context_to_prompt()
    worker._apply_rag_to_prompt()

    assert isinstance(worker.prompt, dict)
    assert "[Authoritative Context]\nKnown fact" in worker.prompt["user"]
    assert "{{AUTHORING_CONTEXT}}" not in worker.prompt["user"]
    lookup_context.assert_called_once_with(
        "world.kraken",
        "event-id",
        context_date=42.0,
        active_map_id=None,
    )


@patch("src.gui.widgets.llm_generation_widget.lookup_event_authoring_context")
def test_generation_worker_skips_disabled_event_context(lookup_context) -> None:
    """Opting out performs no authoring-context lookup."""
    request = GenerationRequest(
        prompt={"system": "System", "user": "[Event]\nName: Eclipse\n\n[Task]\nX"},
        max_tokens=100,
        temperature=0.7,
        db_path="world.kraken",
        target_id="event-id",
        object_type="event",
        authoring_context_enabled=False,
        rag_enabled=False,
    )
    worker = GenerationWorker(MagicMock(), request.prompt, 100, 0.7, request=request)

    worker._apply_authoring_context_to_prompt()

    lookup_context.assert_not_called()
    assert "AUTHORING_CONTEXT" not in worker.prompt["user"]


@patch(
    "src.gui.widgets.llm_generation_widget.format_entity_authoring_context",
    return_value="[Authoritative Context]\nDurable fact",
)
@patch("src.gui.widgets.llm_generation_widget.lookup_entity_authoring_context")
def test_generation_worker_injects_entity_context_independently_of_spatial(
    lookup_context,
    _format_context,
) -> None:
    lookup_context.return_value = MagicMock()
    request = GenerationRequest(
        prompt={
            "system": "System",
            "user": (
                "[Entity]\nName: Ada\n\n{{AUTHORING_CONTEXT}}\n\n"
                "{{SPATIAL_CONTEXT}}\n\n[Task]\nRevise"
            ),
        },
        db_path="world.kraken",
        target_id="entity-id",
        object_type="entity",
        authoring_context_enabled=True,
        spatial_enabled=False,
        rag_enabled=False,
    )
    worker = GenerationWorker(MagicMock(), request.prompt, 100, 0.7, request=request)

    worker._apply_authoring_context_to_prompt()

    assert isinstance(worker.prompt, dict)
    assert "[Authoritative Context]\nDurable fact" in worker.prompt["user"]
    lookup_context.assert_called_once_with("world.kraken", "entity-id")


@pytest.fixture
def clean_settings(tmp_path):
    original_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.clear()
    yield
    settings.clear()
    QSettings.setDefaultFormat(original_format)


@pytest.fixture
def widget(qtbot, clean_settings):
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    # widget.show()  # Ensure widget is shown for visibility tests
    return widget


def test_initial_state(widget):
    """Test initial state of the widget."""
    assert widget.generate_btn.isEnabled()
    assert not widget.cancel_btn.isEnabled()
    assert not widget.custom_prompt_edit.isHidden()
    assert widget.rag_cb.isChecked() is True  # RAG defaults to True


def test_theme_change_refreshes_local_panel_styles(widget):
    """An open LLM panel should refresh its theme-derived local styles."""
    from src.core.theme_manager import ThemeManager

    ThemeManager().set_theme("light_mode")

    assert "#E0E0E0" in widget.top_sep.styleSheet()
    assert "#757575" in widget.lbl_instruction.styleSheet()
    assert "#005A9E" in widget.spatial_show_btn.styleSheet()


def test_malformed_generation_settings_fall_back(qtbot, clean_settings):
    """Malformed generation settings must not prevent widget construction."""
    malformed_values = {
        "ai_gen_last_provider": [],
        "ai_gen_max_tokens": "many",
        "ai_gen_temperature": False,
        "ai_gen_rag_enabled": "unknown",
        "ai_gen_spatial_enabled": 7,
        "ai_gen_rag_limit": None,
    }

    def mock_value(key, default=None, type=None):
        return malformed_values.get(key, default)

    with patch.object(QSettings, "value", side_effect=mock_value):
        generation_widget = LLMGenerationWidget()
        qtbot.addWidget(generation_widget)

    assert generation_widget.provider_combo.currentText() == "LM Studio"
    assert generation_widget.max_tokens_spin.value() == 512
    assert generation_widget.temperature_spin.value() == 70
    assert generation_widget.rag_cb.isChecked() is True
    assert generation_widget.spatial_cb.isChecked() is False
    assert generation_widget.rag_limit_input.text() == "3"


@patch("src.gui.widgets.llm_generation_widget.GenerationWorker")
@patch("src.gui.widgets.llm_generation_widget.create_provider")
def test_generation_flow_custom_prompt(
    mock_create_provider, mock_worker_cls, widget, qtbot
):
    """Test generation with a custom prompt using mocked worker."""
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider.health_check.return_value = {"status": "healthy"}
    mock_create_provider.return_value = mock_provider

    # Setup mock worker instance
    mock_worker = MagicMock()
    mock_worker_cls.return_value = mock_worker

    # Configure widget
    widget.custom_prompt_edit.setPlainText("Custom prompt")
    widget.rag_cb.setChecked(False)  # Disable RAG

    # Mock context
    with patch.object(widget, "_get_generation_context") as mock_ctx:
        mock_ctx.return_value = {"name": "Test", "type": "Item"}

        # Simulate the Review Dialog to accept the result
        with patch(
            "src.gui.dialogs.generation_review_dialog.GenerationReviewDialog"
        ) as MockDialog:
            mock_dlg_instance = MockDialog.return_value
            mock_dlg_instance.get_review_result.return_value = (
                GenerationReviewResult(
                    action=GenerationApplyMode.REPLACE,
                    text="Generated text",
                )
            )

            # Watch for the final signal
            with qtbot.waitSignal(widget.text_generated, timeout=1000) as blocker:
                widget.generate_btn.click()

                # Check that worker was started
                mock_worker.start.assert_called_once()

                # Manually emit completion signal from worker to simulate thread finishing
                # We need to get the slot connected to generation_complete
                # In the code: self._worker.generation_complete.connect(self._on_generation_complete)
                # So we can just call the widget's slot directly or emit the mock signal if properly setup.
                # But since we mocked the CLASS, mock_worker.generation_complete is a MagicMock.
                # We need to manually invoke the callback that was connected to it.

                # Retrieve the callback connected to generation_complete
                # args[0] of connect call
                connect_call = mock_worker.generation_complete.connect.call_args
                callback = connect_call[0][0]
                callback(ModelReply(content="Generated text"))

    # Verify signal verified by waitSignal
    assert blocker.signal_triggered
    emitted = blocker.args[0]
    assert emitted.action == GenerationApplyMode.REPLACE
    assert emitted.text == "Generated text"

    # Verify UI state reset
    assert not widget.cancel_btn.isEnabled()
    assert widget.generate_btn.isEnabled()


def test_generation_review_audit_preserves_raw_and_edited_text(widget):
    """Generation and review events should retain distinct text snapshots."""
    context = {
        "name": "Test",
        "object_type": "entity",
        "object_id": "entity-1",
        "existing_description": "Old description",
    }
    widget._generation_target_id = "entity-1"
    widget._generation_source_hash = widget._hash_source_description(context)
    widget._audit_interaction_id = "interaction-1"
    widget._audit_provider_id = "lmstudio"
    widget._audit_template = {"template_id": "revise"}

    worker = MagicMock()
    worker.prompt = {"system": "System", "user": "Exact prompt"}
    worker.rag_context_used = "Relevant lore"
    worker.spatial_context_used = None
    worker.spatial_enabled = False
    worker.max_tokens = 512
    worker.temperature = 0.7
    worker.rag_limit = 3
    worker.db_path = "world.kraken"
    worker.object_type = "entity"
    worker.active_map_id = None
    worker.provider.get_model_name.return_value = "configured-model"
    widget._worker = worker

    review_result = GenerationReviewResult(
        action=GenerationApplyMode.REPLACE,
        text="User-edited response",
        rating=-1,
        comment="Missed the requested tone",
    )
    with patch.object(
        widget, "_get_generation_context", return_value=context
    ), patch(
        "src.gui.dialogs.generation_review_dialog.GenerationReviewDialog"
    ) as dialog_cls, patch(
        "src.gui.widgets.llm_generation_widget.log_generation_event"
    ) as generation_log, patch(
        "src.gui.widgets.llm_generation_widget.log_review_event"
    ) as review_log:
        dialog = dialog_cls.return_value
        dialog.action = GenerationApplyMode.REPLACE
        dialog.get_review_result.return_value = review_result

        widget._on_generation_complete(
            ModelReply(content="Raw model response", model="reply-model")
        )

    generation_kwargs = generation_log.call_args.kwargs
    review_kwargs = review_log.call_args.kwargs
    assert generation_kwargs["interaction_id"] == "interaction-1"
    assert generation_kwargs["prompt"]["user"] == "Exact prompt"
    assert generation_kwargs["response"]["content"] == "Raw model response"
    assert generation_kwargs["context"]["rag"] == "Relevant lore"
    assert review_kwargs["interaction_id"] == "interaction-1"
    assert review_kwargs["action"] == "replace"
    assert review_kwargs["raw_text"] == "Raw model response"
    assert review_kwargs["presented_text"] == "Raw model response"
    assert review_kwargs["reviewed_text"] == "User-edited response"
    assert review_kwargs["rating"] == -1
    assert review_kwargs["comment"] == "Missed the requested tone"


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_rag_service_called(mock_rag_cls, widget, qtbot):
    """Test that RAG service is instantiated and called when enabled."""
    # Setup mock
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = "Retrieved Context"

    # Configure widget with RAG enabled
    widget.rag_cb.setChecked(True)
    widget.db_path = "dummy.db"
    widget.custom_prompt_edit.setPlainText("Test Prompt")

    # We need to test the worker's execution path.
    # Since worker is threaded, we can verify _apply_rag_to_prompt behavior
    # if we access the worker or simulate the run.
    # Alternatively, we can patch the worker class in the widget
    # but RAG is instantiated inside the worker.
    # Easier: Instantiate the worker directly and call _apply_rag_to_prompt

    from src.gui.widgets.llm_generation_widget import GenerationWorker

    # Create worker provided with a prompt
    worker = GenerationWorker(
        provider=MagicMock(),
        prompt="Test Prompt",
        max_tokens=100,
        temperature=0.7,
        db_path="dummy.db",
        rag_limit=3,
    )

    # Run the private method synchronously
    worker._apply_rag_to_prompt()

    # Verify RAG Service usage
    mock_rag_cls.assert_called_with("dummy.db")
    mock_service.get_context.assert_called_with(
        "Test Prompt", top_k=3, exclude_names=[]
    )

    # Verify prompt modification
    assert "[Context]" in worker.prompt
    assert "Retrieved Context" in worker.prompt


def test_generation_worker_rejects_malformed_structured_prompt():
    """Malformed structured prompts fail at the worker boundary."""
    with pytest.raises(TypeError, match="string 'system' and 'user' values"):
        GenerationWorker(
            provider=MagicMock(),
            prompt={"system": "Valid", "user": {"invalid": "value"}},  # type: ignore[dict-item]
            max_tokens=100,
            temperature=0.7,
        )


def test_generation_worker_copies_structured_prompt():
    """Worker prompt mutation must not alter the caller's request object."""
    prompt = {"system": "System", "user": "User {{RAG_CONTEXT}}"}
    worker = GenerationWorker(
        provider=MagicMock(),
        prompt=prompt,
        max_tokens=100,
        temperature=0.7,
    )

    prompt["user"] = "Changed"

    assert worker.prompt == {
        "system": "System",
        "user": "User {{RAG_CONTEXT}}",
    }


def test_empty_custom_prompt_error(widget):
    """Test error when custom prompt is enabled but empty."""
    # Mock context retrieval to pass the first check
    with patch.object(widget, "_get_generation_context") as mock_ctx:
        mock_ctx.return_value = {"name": "Test"}

        widget.custom_prompt_edit.setPlainText("")

        widget.generate_btn.click()

        assert "empty" in widget.status_label.text().lower()


@patch("src.services.llm_provider.get_provider_settings_from_qsettings")
def test_settings_usage(mock_get_settings, widget):
    """Verify widget attempts to load settings correctly."""
    # This tests the _get_provider_id logic implicitly if we had more providers
    # For now just verify it defaults correctly
    assert widget._get_provider_id() == "lmstudio"


def _task_template() -> TaskTemplate:
    return TaskTemplate(
        template_id="create_test",
        name="Create — Test",
        description="Create a test description",
        intent=TaskIntent.CREATE,
        content="Template content for {name}",
        source=TaskTemplateSource.BUILT_IN,
    )


def test_template_combo_uses_injected_snapshot(widget):
    """The widget lists templates supplied by the app manager."""
    widget.custom_prompt_edit.setPlainText("Existing custom draft")
    widget.set_task_templates((_task_template(),))

    assert widget.template_combo.count() == 2
    assert widget.template_combo.itemData(0) is None
    assert widget.template_combo.findData("create_test") == 1


def test_template_requires_explicit_use_and_edits_become_custom(widget):
    """Selecting is safe; applying copies content; editing detaches the task."""
    widget.custom_prompt_edit.setPlainText("Keep this draft")
    widget.set_task_templates((_task_template(),))
    widget.template_combo.setCurrentIndex(1)

    assert widget.custom_prompt_edit.toPlainText() == "Keep this draft"

    widget.use_template_btn.click()
    assert widget.custom_prompt_edit.toPlainText() == "Template content for {name}"
    assert widget.template_combo.currentData() == "create_test"

    widget.custom_prompt_edit.setPlainText("Edited task")
    assert widget.template_combo.currentData() is None


def test_initial_selection_is_custom(qtbot, clean_settings):
    """Without a coordinator snapshot the safe initial state is Custom task."""
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)

    assert widget.template_combo.count() == 1
    assert widget.template_combo.itemData(0) is None
    assert widget.template_combo.currentIndex() == 0


def test_recommends_create_or_update_without_crossing_object_drafts(
    qtbot, clean_settings
):
    """Entity and event selectors use independent per-world preference keys."""
    create = TaskTemplate(
        template_id="create_complete_description",
        name="Create — Complete Description",
        description="Create a complete description",
        intent=TaskIntent.CREATE,
        content="Create {name}",
        source=TaskTemplateSource.BUILT_IN,
    )
    revise = TaskTemplate(
        template_id="revise_clarity_flow",
        name="Revise — Clarity and Flow",
        description="Revise a test description",
        intent=TaskIntent.UPDATE,
        content="Revise {description}",
        source=TaskTemplateSource.BUILT_IN,
    )
    condense = TaskTemplate(
        template_id="condense_essential_version",
        name="Condense — Essential Version",
        description="Condense a test description",
        intent=TaskIntent.UPDATE,
        content="Condense {description}",
        source=TaskTemplateSource.BUILT_IN,
    )

    class Provider:
        def __init__(self, context):
            self.context = context

        def get_generation_context(self):
            return dict(self.context)

    entity = LLMGenerationWidget(
        context_provider=Provider(
            {"object_type": "entity", "existing_description": ""}
        )
    )
    event = LLMGenerationWidget(
        context_provider=Provider(
            {"object_type": "event", "existing_description": "Existing"}
        )
    )
    qtbot.addWidget(entity)
    qtbot.addWidget(event)
    # Catalog order must not make the first generic update task the recommendation.
    entity.set_task_templates((condense, create, revise))
    event.set_task_templates((condense, create, revise))

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    assert entity.template_combo.currentData() == "create_complete_description"
    assert event.template_combo.currentData() == "revise_clarity_flow"
    assert settings.value("ai_gen_entity_template_id") == (
        "create_complete_description"
    )
    assert settings.value("ai_gen_event_template_id") == "revise_clarity_flow"
