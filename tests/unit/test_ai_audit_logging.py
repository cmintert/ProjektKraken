"""Unit tests for structured AI audit logging."""

import json
import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.core.logging_config import (
    AUDIT_LOG_FILENAME,
    get_audit_logger,
    setup_audit_logging,
)
from src.services.ai_audit_service import (
    log_generation_event,
    log_review_event,
)


@pytest.fixture(autouse=True)
def _clean_audit_logger():
    """Remove global audit handlers between tests."""
    audit_logger = logging.getLogger("ai_audit")
    for handler in audit_logger.handlers[:]:
        handler.close()
    audit_logger.handlers.clear()
    yield
    for handler in audit_logger.handlers[:]:
        handler.close()
    audit_logger.handlers.clear()


@pytest.fixture
def audit_settings():
    """Provide QSettings helpers for toggling audit logging."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    yield settings
    settings.remove("ai_gen_audit_log")


def _flush_audit_logger() -> None:
    for handler in logging.getLogger("ai_audit").handlers:
        handler.flush()


def _close_audit_logger() -> None:
    audit_logger = logging.getLogger("ai_audit")
    for handler in audit_logger.handlers[:]:
        handler.close()
    audit_logger.handlers.clear()


def test_get_audit_logger_returns_named_logger():
    """The global audit logger should have its dedicated name."""
    assert get_audit_logger().name == "ai_audit"


def test_setup_audit_logging_is_idempotent_and_does_not_propagate():
    """Repeated setup should retain one isolated audit handler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()
            setup_audit_logging()

    audit = logging.getLogger("ai_audit")
    assert len(audit.handlers) == 1
    assert audit.propagate is False


def test_disabled_auditing_does_not_create_file(audit_settings):
    """No delayed audit file should be created while auditing is disabled."""
    audit_settings.setValue("ai_gen_audit_log", False)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()
            written = log_generation_event(
                interaction_id="interaction-1",
                prompt={"system": "System", "user": "Task"},
                source="test",
                provider="local",
                model="model",
                status="success",
                response={"content": "Response"},
            )

        assert written is False
        assert not os.path.exists(os.path.join(tmpdir, AUDIT_LOG_FILENAME))


def test_generation_event_is_one_parseable_json_line(audit_settings):
    """Generation data should be structured, complete, and parseable."""
    audit_settings.setValue("ai_gen_audit_log", True)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()
            written = log_generation_event(
                interaction_id="interaction-1",
                prompt={"system": "System", "user": "Task"},
                source="LLMGenerationWidget",
                provider="lmstudio",
                model="test-model",
                status="success",
                response={"content": "Raw response", "usage": {"total": 12}},
                parameters={"temperature": 0.7, "max_tokens": 512},
                template={"template_id": "revise", "content_hash": "abc"},
                target={"target_id": "entity-1", "object_type": "entity"},
                context={"rag": "Retrieved lore", "spatial": None},
                duration_ms=125,
            )
            _flush_audit_logger()

        with open(
            os.path.join(tmpdir, AUDIT_LOG_FILENAME), encoding="utf-8"
        ) as audit_file:
            lines = audit_file.readlines()
        _close_audit_logger()

    assert written is True
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["schema_version"] == 1
    assert record["event"] == "generation_completed"
    assert record["interaction_id"] == "interaction-1"
    assert record["prompt"] == {"system": "System", "user": "Task"}
    assert len(record["prompt_hash"]) == 64
    assert record["response"]["content"] == "Raw response"
    assert record["template"]["template_id"] == "revise"
    assert record["context"]["rag"] == "Retrieved lore"


def test_review_event_captures_decision_feedback_and_edits(audit_settings):
    """Review records should distinguish filtering from user edits."""
    audit_settings.setValue("ai_gen_audit_log", True)
    fake_logger = MagicMock(spec=logging.Logger)
    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ):
        written = log_review_event(
            interaction_id="interaction-1",
            action="replace",
            raw_text="<think>hidden</think>Draft",
            presented_text="Draft",
            reviewed_text="Improved draft",
            source="LLMGenerationWidget",
            rating=-1,
            comment="Needed a clearer opening",
            audit_path="/world/ai_audit_log.jsonl",
        )

    record = json.loads(fake_logger.info.call_args.args[0])
    assert written is True
    assert record["event"] == "review_completed"
    assert record["action"] == "replace"
    assert record["accepted"] is True
    assert record["rating"] == -1
    assert record["comment"] == "Needed a clearer opening"
    assert record["automatic_filter_changed"] is True
    assert record["user_edited"] is True
    assert record["reviewed_text"] == "Improved draft"
    assert record["presented_to_reviewed_similarity"] < 1


def test_discard_is_recorded_as_refused(audit_settings):
    """Discarded output should remain analysable as an explicit refusal."""
    audit_settings.setValue("ai_gen_audit_log", True)
    fake_logger = MagicMock(spec=logging.Logger)
    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ):
        log_review_event(
            interaction_id="interaction-2",
            action="discard",
            raw_text="Draft",
            presented_text="Draft",
            reviewed_text="Draft",
            source="LLMGenerationWidget",
            audit_path="/world/ai_audit_log.jsonl",
        )

    record = json.loads(fake_logger.info.call_args.args[0])
    assert record["accepted"] is False
    assert record["action"] == "discard"
