"""Shared HTTP/stdio catalogue for opt-in local generation experiments."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from src.integrations.mcp.results import tool_adapter


def register_generation_tools(
    server: MCPServer,
    call: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    """Register bounded job starts and evidence reads, never world mutations."""
    write = ToolAnnotations(read_only_hint=False, destructive_hint=False)
    read = ToolAnnotations(read_only_hint=True, destructive_hint=False)

    @server.tool(annotations=write)
    @tool_adapter
    async def prepare_generation_experiment(
        kind: Literal["entity", "event"],
        target_id: str,
        idempotency_key: str,
        task: str = "",
        template_id: str | None = None,
        context_mode: Literal[
            "all_history", "at_playhead", "history_to_playhead"
        ] = "all_history",
        lore_day: float | None = None,
        active_map_id: str | None = None,
        operation: Literal[
            "custom",
            "create",
            "revise",
            "condense",
            "expand_grounded",
            "expand_creative",
        ] = "custom",
        include_undated: bool = False,
        include_world_context: bool | None = None,
        include_retrieved: bool | None = None,
        include_spatial: bool | None = None,
    ) -> dict[str, Any]:
        """Freeze saved inputs for local trials. Poll the returned experiment ID."""
        return await call(
            "prepare_generation_experiment",
            {
                "kind": kind,
                "target_id": target_id,
                "idempotency_key": idempotency_key,
                "task": task,
                "template_id": template_id,
                "context_mode": context_mode,
                "lore_day": lore_day,
                "active_map_id": active_map_id,
                "operation": operation,
                "include_undated": include_undated,
                "include_world_context": include_world_context,
                "include_retrieved": include_retrieved,
                "include_spatial": include_spatial,
            },
        )

    @server.tool(annotations=read)
    @tool_adapter
    async def get_generation_experiment(
        experiment_id: str,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Read frozen experiment JSON in lossless text pages; follow next_offset."""
        return await call(
            "get_generation_experiment",
            {
                "experiment_id": experiment_id,
                "offset": offset,
            },
        )

    @server.tool(annotations=write)
    @tool_adapter
    async def start_generation_trial(
        experiment_id: str,
        idempotency_key: str,
        variant: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run baseline or temporary order/headings/instruction/separator variant.

        Retained block IDs must appear once. Optional authoring/retrieved/spatial
        blocks may be excluded with exclude; max_tokens overrides output allowance. Facts and
        application policy cannot be replaced. No run or experiment-count quotas apply.
        """
        return await call(
            "start_generation_trial",
            {
                "experiment_id": experiment_id,
                "idempotency_key": idempotency_key,
                "variant": variant,
            },
        )

    @server.tool(annotations=read)
    @tool_adapter
    async def get_generation_trial(
        experiment_id: str,
        trial_id: str,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Poll a trial and read exact messages/output without applying content."""
        return await call(
            "get_generation_trial",
            {
                "experiment_id": experiment_id,
                "trial_id": trial_id,
                "offset": offset,
            },
        )

    @server.tool(annotations=write)
    @tool_adapter
    async def cancel_generation_experiment(experiment_id: str) -> dict[str, Any]:
        """Cancel the experiment and its active work; retained evidence is session-only."""
        return await call(
            "cancel_generation_experiment", {"experiment_id": experiment_id}
        )
