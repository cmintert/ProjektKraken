"""Structured per-world audit logging for AI generation and review outcomes."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

AI_AUDIT_SCHEMA_VERSION = 1
MAX_RATING_COMMENT_LENGTH = 200


def new_interaction_id() -> str:
    """Return a unique identifier linking generation and review events."""
    return str(uuid.uuid4())


def log_generation_event(
    *,
    interaction_id: str,
    prompt: object,
    source: str,
    provider: str,
    model: str,
    status: str,
    response: dict[str, Any] | None = None,
    error: str | None = None,
    parameters: dict[str, Any] | None = None,
    template: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    audit_path: str | None = None,
) -> bool:
    """Write one model-generation event to the JSONL audit log.

    Args:
        interaction_id: Identifier shared with the later review event.
        prompt: Exact prompt sent to the provider after context injection.
        source: Feature which requested generation.
        provider: Provider identifier.
        model: Model identifier returned by the provider or configuration.
        status: Generation outcome such as ``success`` or ``error``.
        response: Provider-neutral raw response snapshot.
        error: Error message for unsuccessful generation.
        parameters: Generation settings such as temperature and token limit.
        template: Selected task-template identity and content hash.
        target: Target object identity and source-content hash.
        context: Separately captured RAG and spatial context.
        duration_ms: Elapsed generation duration in milliseconds.
        audit_path: Optional world-local JSONL path.

    Returns:
        True when the event was handed to an audit logger, otherwise False.
    """
    prompt_snapshot = _json_safe(prompt)
    payload: dict[str, Any] = {
        "event": "generation_completed",
        "interaction_id": interaction_id,
        "source": source,
        "provider": provider,
        "model": model,
        "status": status,
        "prompt": prompt_snapshot,
        "prompt_hash": _stable_hash(prompt_snapshot),
        "response": _json_safe(response) if response is not None else None,
        "error": error,
        "parameters": _json_safe(parameters or {}),
        "template": _json_safe(template) if template else None,
        "target": _json_safe(target) if target else None,
        "context": _json_safe(context or {}),
        "duration_ms": duration_ms,
    }
    return _write_event(payload, audit_path)


def log_review_event(
    *,
    interaction_id: str,
    action: str,
    raw_text: str,
    presented_text: str,
    reviewed_text: str,
    source: str,
    rating: int | None = None,
    comment: str | None = None,
    audit_path: str | None = None,
) -> bool:
    """Write the user's review decision and edits for a generation.

    The raw, presented, and reviewed texts are intentionally distinct. This
    allows later analysis to separate provider output, automatic filtering,
    and deliberate user edits.
    """
    normalized_rating = rating if rating in {-1, 1} else None
    normalized_comment = (comment or "").strip()[:MAX_RATING_COMMENT_LENGTH] or None
    payload: dict[str, Any] = {
        "event": "review_completed",
        "interaction_id": interaction_id,
        "source": source,
        "action": action,
        "accepted": action in {"replace", "append", "automatic"},
        "rating": normalized_rating,
        "comment": normalized_comment,
        "raw_text": raw_text,
        "presented_text": presented_text,
        "reviewed_text": reviewed_text,
        "automatic_filter_changed": raw_text != presented_text,
        "user_edited": presented_text != reviewed_text,
        "raw_to_reviewed_similarity": _similarity(raw_text, reviewed_text),
        "presented_to_reviewed_similarity": _similarity(
            presented_text, reviewed_text
        ),
        "raw_length": len(raw_text),
        "presented_length": len(presented_text),
        "reviewed_length": len(reviewed_text),
    }
    return _write_event(payload, audit_path)


def _write_event(payload: dict[str, Any], audit_path: str | None) -> bool:
    """Serialize an audit event as one JSON line when auditing is enabled."""
    try:
        if not _audit_enabled():
            return False

        if audit_path:
            from src.core.logging_config import get_audit_logger_for_path

            audit = get_audit_logger_for_path(audit_path)
        else:
            from src.core.logging_config import get_audit_logger

            audit = get_audit_logger()

        record = {
            "schema_version": AI_AUDIT_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        audit.info(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return True
    except Exception as exc:
        logger.warning("Could not write AI audit event: %s", exc, exc_info=True)
        return False


def _audit_enabled() -> bool:
    """Return whether the user enabled AI audit logging."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    return bool(settings.value("ai_gen_audit_log", False, type=bool))


def _json_safe(value: object) -> Any:
    """Return a recursively JSON-serializable snapshot."""
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return str(value)


def _stable_hash(value: object) -> str:
    """Return a stable SHA-256 hash for a JSON-compatible value."""
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _similarity(before: str, after: str) -> float:
    """Return a stable 0-1 similarity ratio for two text snapshots."""
    return round(SequenceMatcher(None, before, after, autojunk=False).ratio(), 6)
