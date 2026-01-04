"""
Resilience Utilities Module.

Provides fault tolerance patterns like circuit breakers for robust API interactions.
"""

import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Simple circuit breaker implementation for fault tolerance.

    Tracks failures and opens circuit after threshold is reached,
    preventing further requests until a timeout period passes.
    Implements the three-state pattern: closed, open, half-open.
    """

    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            timeout: Seconds to wait before attempting to close circuit.
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            Exception: If circuit is open or function fails.
        """
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info("Circuit breaker entering half-open state")
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is OPEN - too many recent failures")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                logger.info("Circuit breaker closing after successful call")
                self.state = "closed"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker OPENING after {self.failures} failures"
                )
                self.state = "open"

            raise e

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "closed"
        logger.info("Circuit breaker manually reset")

    def get_state(self) -> dict:
        """
        Get current circuit breaker state.

        Returns:
            dict: State information including status, failures, and time since last failure.
        """
        return {
            "state": self.state,
            "failures": self.failures,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": time.time() - self.last_failure_time
            if self.last_failure_time > 0
            else None,
        }
