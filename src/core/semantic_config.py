"""Configuration for semantic completion and provider safety checks."""

from src.core.environment import env_bool, env_float

SEMANTIC_COMPLETION_ENABLE_EMBEDDING = env_bool(
    "PK_SEMANTIC_COMPLETION_ENABLE_EMBEDDING",
    default=True,
)
SEMANTIC_COMPLETION_PROBE_ON_WINDOWS = env_bool(
    "PK_SEMANTIC_COMPLETION_PROBE_ON_WINDOWS",
    default=True,
)
SEMANTIC_COMPLETION_PROBE_TIMEOUT_S = env_float(
    "PK_SEMANTIC_COMPLETION_PROBE_TIMEOUT_S",
    default=15.0,
)
