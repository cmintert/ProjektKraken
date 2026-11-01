"""Headless review reconstruction using the desktop transfer and timing contracts."""

from __future__ import annotations

from typing import Any

from src.commands.base_command import BaseCommand
from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.commands.event_timing_intents import request_for_command
from src.commands.transfer_commands import ApplyTransferCommand
from src.services.db_service import DatabaseService
from src.services.event_timing.planning import TimingChangePlan, prepare_change
from src.services.event_timing.store import capture, register
from src.services.transfer_exchange import load_sources
from src.services.transfer_import import prepare_import

REVIEW_REQUIRED = 3


def prepare_review(
    db: DatabaseService,
    source: str,
    options: dict[str, Any],
) -> tuple[dict[str, Any], TimingChangePlan | None]:
    """Prepare from original files; no artifact-supplied row changes are accepted."""
    data = load_sources([{"path": source}])
    preview = prepare_import(db, data, options)
    if preview["errors"]:
        return preview, None
    command = ApplyTransferCommand(preview)
    if not any(item["table"] == "events" for item in preview["delta"]):
        return preview, None
    state = capture(db)
    plan = prepare_change(state, request_for_command(command, state))
    preview["errors"].extend(plan.errors)
    needs_review = bool((preview.get("timing_review") or {}).get("needs_review"))
    preview["timing_review"] = plan.review()
    preview["timing_review"]["needs_review"] |= needs_review
    return preview, plan


def review_artifact(source: str, preview: dict[str, Any]) -> dict[str, Any]:
    """Record intent and fingerprints only, never executable deltas or SQL."""
    return {
        "schema": 1,
        "source": source,
        "db_path": preview.get("db_path"),
        "source_hashes": preview.get("source_hashes", {}),
        "revision": preview.get("revision"),
        "context_revision": preview.get("context_revision"),
        "options": preview["options"],
        "timing_fingerprint": (preview.get("timing_review") or {}).get("fingerprint"),
    }


def verify_artifact(artifact: dict[str, Any], fresh: dict[str, Any]) -> None:
    """An edited source, world, context or reviewed intent needs a new review."""
    if artifact.get("schema") != 1 or artifact != fresh:
        raise ValueError("Review inputs changed. Generate and inspect a fresh review.")


def reviewed_command(
    db: DatabaseService,
    preview: dict[str, Any],
    plan: TimingChangePlan | None,
) -> BaseCommand:
    """Use the same internally registered prepared command as desktop authoring."""
    command: BaseCommand = ApplyTransferCommand(preview)
    if plan is not None:
        identity = register(db, plan)
        command = ApplyEventTimingPlanCommand(command, identity, plan.fingerprint)
    return command
