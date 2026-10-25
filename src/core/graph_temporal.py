"""Compatibility facade for the shared relation temporal policy."""

from src.core.temporal_relation_policy import (
    RelationTemporalMode as GraphTemporalMode,
)
from src.core.temporal_relation_policy import (
    evaluate_temporal_relation as evaluate_graph_relation,
)

__all__ = ["GraphTemporalMode", "evaluate_graph_relation"]
