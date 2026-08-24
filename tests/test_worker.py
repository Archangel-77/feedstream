import json
import uuid

import pytest
from sqlalchemy import select

from feedstream import worker as worker_module
from feedstream.models import Event
from feedstream.worker import (
    CircuitBreaker,
    _connect_and_consume_with_retry,
    _handle_signal,
    _shutdown,
    ingest_loop,
    parse_ais_message,
    write_event,
)


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


# --- parse_ais_message ---


def test_parse_ais_message_rejects_non_json():
    assert parse_ais_message("this is not json") is None


def test_parse_ais_message_missing_metadata_has_no_dedup_key():
    event = parse_ais_message(json.dumps({"MessageType": "PositionReport", "Message": {}}))
    assert event is not None
    assert event["dedup_key"] is None


def test_parse_ais_message_builds_dedup_key():
    raw = json.dumps(
        {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789, "time_utc": "2024-01-01 00:00:00"},
        }
    )
    event = parse_ais_message(raw)
    assert event is not None
    assert event["dedup_key"] == "123456789:PositionReport:2024-01-01 00:00:00"
    assert event["source"] == "aisstream"
    assert event["event_type"] == "PositionReport"


# --- dedup idempotency ---


@pytest.mark.asyncio
async def test_write_same_event_twice_stores_one_row(db_session, patched_worker_redis):
    """The core idempotency claim: replayed events are not duplicated."""
    raw = json.dumps(
        {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789, "time_utc": "2024-01-01 00:00:00"},
            "Message": {},
        }
    )
    event_dict = parse_ais_message(raw)
    assert event_dict is not None

    assert await write_event(db_session, event_dict) == "inserted"
    assert await write_event(db_session, event_dict) == "duplicate"

    result = await db_session.execute(select(Event))
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_write_event_rejects_missing_dedup_key(db_session, patched_worker_redis):
    """Events without MMSI/time_utc must be skipped, not crash the loop."""
    event_dict = {
        "id": uuid.uuid4(),
        "source": "aisstream",
        "event_type": "PositionReport",
        "payload": {"MessageType": "PositionReport"},
        "dedup_key": None,
    }
    status = await write_event(db_session, event_dict)
    assert status == "rejected"

    result = await db_session.execute(select(Event))
    assert len(result.scalars().all()) == 0


# --- graceful shutdown ---


def test_shutdown_signal_sets_event():
    _shutdown.clear()
    _handle_signal()
    assert _shutdown.is_set()
    _shutdown.clear()


@pytest.mark.asyncio
async def test_ingest_loop_exits_when_shutdown_requested(monkeypatch):
    _shutdown.set()

    async def fake_connect_and_consume():
        raise AssertionError("should not connect when shutdown is requested")

    monkeypatch.setattr(worker_module, "_connect_and_consume", fake_connect_and_consume)
    # Should return immediately without attempting a connection.
    await ingest_loop()
    _shutdown.clear()


# --- retry / backoff ---


@pytest.mark.asyncio
async def test_connect_and_consume_retries_on_connection_closed(monkeypatch):
    """Upstream drops: the worker retries per the tenacity policy and recovers."""
    calls = {"n": 0}

    async def flaky_connect():
        calls["n"] += 1
        if calls["n"] < 3:
            from websockets.exceptions import ConnectionClosed
            from websockets.frames import Close

            raise ConnectionClosed(rcvd=Close(1006, "upstream dropped"), sent=None)
        # Third attempt succeeds.

    monkeypatch.setattr(worker_module, "_connect_and_consume", flaky_connect)
    await _connect_and_consume_with_retry()
    assert calls["n"] == 3
