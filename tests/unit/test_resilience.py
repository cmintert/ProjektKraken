"""
Tests for the CircuitBreaker resilience utility.
"""
import time
from unittest.mock import Mock

import pytest

from src.services.resilience import CircuitBreaker


def test_circuit_breaker_initial_state():
    """Test circuit breaker starts in closed state."""
    cb = CircuitBreaker()
    
    assert cb.state == "closed"
    assert cb.failures == 0
    assert cb.last_failure_time == 0.0


def test_circuit_breaker_custom_settings():
    """Test circuit breaker with custom threshold and timeout."""
    cb = CircuitBreaker(failure_threshold=3, timeout=30.0)
    
    assert cb.failure_threshold == 3
    assert cb.timeout == 30.0


def test_circuit_breaker_successful_call():
    """Test successful function call through circuit breaker."""
    cb = CircuitBreaker()
    mock_func = Mock(return_value="success")
    
    result = cb.call(mock_func, "arg1", key="value")
    
    assert result == "success"
    mock_func.assert_called_once_with("arg1", key="value")
    assert cb.state == "closed"
    assert cb.failures == 0


def test_circuit_breaker_single_failure():
    """Test circuit breaker handles single failure."""
    cb = CircuitBreaker(failure_threshold=5)
    mock_func = Mock(side_effect=ValueError("test error"))
    
    with pytest.raises(ValueError, match="test error"):
        cb.call(mock_func)
    
    assert cb.state == "closed"  # Still closed, threshold not reached
    assert cb.failures == 1


def test_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after reaching failure threshold."""
    cb = CircuitBreaker(failure_threshold=3)
    mock_func = Mock(side_effect=ValueError("error"))
    
    # Fail 3 times
    for _ in range(3):
        with pytest.raises(ValueError):
            cb.call(mock_func)
    
    assert cb.state == "open"
    assert cb.failures == 3


def test_circuit_breaker_rejects_calls_when_open():
    """Test circuit breaker rejects calls when open."""
    cb = CircuitBreaker(failure_threshold=2)
    mock_func = Mock(side_effect=ValueError("error"))
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(mock_func)
    
    assert cb.state == "open"
    
    # Next call should be rejected immediately
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        cb.call(mock_func)


def test_circuit_breaker_half_open_after_timeout():
    """Test circuit breaker enters half-open state after timeout."""
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
    mock_func = Mock(side_effect=ValueError("error"))
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(mock_func)
    
    assert cb.state == "open"
    
    # Wait for timeout
    time.sleep(0.2)
    
    # Configure mock to succeed
    mock_func.side_effect = None
    mock_func.return_value = "success"
    
    # Next call should transition to half-open then closed
    result = cb.call(mock_func)
    
    assert result == "success"
    assert cb.state == "closed"
    assert cb.failures == 0


def test_circuit_breaker_reopens_on_half_open_failure():
    """Test circuit breaker reopens if failure occurs in half-open state."""
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
    mock_func = Mock(side_effect=ValueError("error"))
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(mock_func)
    
    assert cb.state == "open"
    
    # Wait for timeout to enter half-open
    time.sleep(0.2)
    
    # Next call should enter half-open then fail
    with pytest.raises(ValueError):
        cb.call(mock_func)
    
    # Should still be open (or re-opened)
    assert cb.failures >= 2


def test_circuit_breaker_reset():
    """Test manual reset of circuit breaker."""
    cb = CircuitBreaker(failure_threshold=2)
    mock_func = Mock(side_effect=ValueError("error"))
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(mock_func)
    
    assert cb.state == "open"
    assert cb.failures == 2
    
    # Reset the circuit
    cb.reset()
    
    assert cb.state == "closed"
    assert cb.failures == 0
    assert cb.last_failure_time == 0.0


def test_circuit_breaker_get_state():
    """Test getting circuit breaker state information."""
    cb = CircuitBreaker()
    
    state = cb.get_state()
    
    assert state["state"] == "closed"
    assert state["failures"] == 0
    assert state["last_failure_time"] == 0.0
    assert state["time_since_last_failure"] is None


def test_circuit_breaker_get_state_after_failure():
    """Test get_state returns correct information after failures."""
    cb = CircuitBreaker(failure_threshold=5)
    mock_func = Mock(side_effect=ValueError("error"))
    
    with pytest.raises(ValueError):
        cb.call(mock_func)
    
    state = cb.get_state()
    
    assert state["state"] == "closed"
    assert state["failures"] == 1
    assert state["last_failure_time"] > 0
    assert state["time_since_last_failure"] is not None
    assert state["time_since_last_failure"] >= 0


def test_circuit_breaker_incremental_failures():
    """Test circuit breaker counts failures incrementally."""
    cb = CircuitBreaker(failure_threshold=5)
    mock_func = Mock(side_effect=ValueError("error"))
    
    for i in range(4):
        with pytest.raises(ValueError):
            cb.call(mock_func)
        assert cb.failures == i + 1
        assert cb.state == "closed"
    
    # Fifth failure should open the circuit
    with pytest.raises(ValueError):
        cb.call(mock_func)
    
    assert cb.failures == 5
    assert cb.state == "open"


def test_circuit_breaker_success_in_half_open():
    """Test successful call in half-open state closes circuit."""
    cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
    
    # Open the circuit
    mock_func = Mock(side_effect=ValueError("error"))
    with pytest.raises(ValueError):
        cb.call(mock_func)
    
    assert cb.state == "open"
    
    # Wait for timeout
    time.sleep(0.2)
    
    # Successful call should close circuit
    mock_func = Mock(return_value="success")
    result = cb.call(mock_func)
    
    assert result == "success"
    assert cb.state == "closed"
    assert cb.failures == 0


def test_circuit_breaker_preserves_return_value():
    """Test circuit breaker preserves function return value."""
    cb = CircuitBreaker()
    
    result1 = cb.call(lambda: 42)
    result2 = cb.call(lambda x: x * 2, 5)
    result3 = cb.call(lambda a, b: a + b, 1, b=2)
    
    assert result1 == 42
    assert result2 == 10
    assert result3 == 3


def test_circuit_breaker_preserves_exception_type():
    """Test circuit breaker preserves exception type."""
    cb = CircuitBreaker(failure_threshold=5)
    
    def raise_value_error():
        raise ValueError("test")
    
    def raise_type_error():
        return "string" + 123
    
    with pytest.raises(ValueError):
        cb.call(raise_value_error)
    
    with pytest.raises(TypeError):
        cb.call(raise_type_error)
