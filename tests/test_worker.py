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
    
    # First failure should raise original exception (circuit not open yet)
    with pytest.raises(Exception, match="failed"):
        cb.call(lambda: exec("raise Exception('failed')"))
    
    # Second failure should open the circuit and raise circuit breaker exception
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
    
    # Check state to trigger transition
    cb.check_state()
    
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
    
    # Wait for timeout and check state to trigger transition
    import time
    time.sleep(1)
    cb.check_state()
    
    # Should reset on successful call
    result = cb.call(lambda: "success")
    assert result == "success"
    assert cb.state == "CLOSED"
