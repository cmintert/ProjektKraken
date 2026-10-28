"""Noninteractive prepare/confirm/apply support for Event timing mutations."""

import json

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.commands.event_timing_intents import request_for_command
from src.services.db_service import DatabaseService
from src.services.event_timing.planning import prepare_change
from src.services.event_timing.store import capture, register


def execute_timing(
    command: BaseCommand, db: DatabaseService, confirmation: str | None = None
) -> CommandResult:
    """Calculate synchronously; explicit fingerprints authorize reviewed cascades."""
    snapshot = capture(db)
    try:
        request = request_for_command(command, snapshot)
        plan = prepare_change(snapshot, request)
        if plan.errors:
            return CommandResult(False, "\n".join(plan.errors))
        if plan.needs_review and confirmation != plan.fingerprint:
            return CommandResult(
                False,
                "Timing review required. Repeat with --confirm-timing "
                + plan.fingerprint
                + "\n"
                + json.dumps(plan.review(), indent=2),
                data={"timing_review": plan.review()},
            )
        register(db, plan)
        return ApplyEventTimingPlanCommand(
            command, plan.identity, plan.fingerprint
        ).execute(db)
    except (ValueError, TypeError, KeyError) as exc:
        return CommandResult(False, str(exc))
