import sys

from src.performance.resources import process_memory_bytes, system_cpu_percent


def test_resource_sampling_is_non_negative() -> None:
    memory = process_memory_bytes()
    cpu = system_cpu_percent(sample_seconds=0.01)

    if sys.platform == "win32":
        assert memory["working_set"] is not None
        assert memory["working_set"] > 0
        assert memory["private_bytes"] is not None
        assert memory["private_bytes"] > 0
    assert cpu is None or 0.0 <= cpu <= 100.0
