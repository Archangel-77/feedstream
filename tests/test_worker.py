import pytest
from unittest.mock import patch, MagicMock
from feedstream.worker import CircuitBreaker


def test_circuit_breaker_closed():
    """Test that circuit breaker starts in closed state and allows calls."""
    cb = CircuitBreaker()
    assert cb.state == "CLOSED"
    
    # Should not raise exception on successful call
    result = cb.call(lambda: "success")
    assert result == "success"
    assert cb.state == "CLOSED"


def test_circuit_breaker_open():
    """Test that circuit breaker opens after threshold failures."""
    cb = CircuitBreaker(failure_threshold=2, timeout=1)
    
    # First failure
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        cb.call(lambda: exec("raise Exception('failed')"))
    
    # Second failure should open the circuit
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        cb.call(lambda: exec("raise Exception('failed')"))
    
    assert cb.state == "OPEN"


def test_circuit_breaker_half_open():
    """Test that circuit breaker transitions to half-open after timeout."""
    cb = CircuitBreaker(failure_threshold=1, timeout=1)
    
    # First failure should open circuit
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        cb.call(lambda: exec("raise Exception('failed')"))
    
    assert cb.state == "OPEN"
    
    # Wait for timeout
    import time
    time.sleep(1)
    
    # Should be half-open now
    assert cb.state == "HALF_OPEN"
    
    # First call in half-open should succeed
    result = cb.call(lambda: "success")
    assert result == "success"
    assert cb.state == "CLOSED"


def test_circuit_breaker_reset_on_success():
    """Test that circuit breaker resets on successful call after being open."""
    cb = CircuitBreaker(failure_threshold=1, timeout=1)
    
    # First failure should open circuit
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        cb.call(lambda: exec("raise Exception('failed')"))
    
    # Should reset on successful call
    result = cb.call(lambda: "success")
    assert result == "success"
    assert cb.state == "CLOSED"
