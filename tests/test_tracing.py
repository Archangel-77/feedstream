import uuid

import pytest
from httpx import AsyncClient

from feedstream.observability.tracing import get_correlation_id, set_ingestion_trace_id


@pytest.mark.asyncio
async def test_request_id_propagates_from_input_header(client: AsyncClient):
    request_id = "req-test-123"
    response = await client.get("/healthz", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.asyncio
async def test_request_id_generated_when_header_absent(client: AsyncClient):
    response = await client.get("/healthz")
    assert response.status_code == 200
    generated = response.headers.get("X-Request-ID")
    assert generated
    uuid.UUID(generated)  # must be a valid UUID


@pytest.mark.asyncio
async def test_get_correlation_id_falls_back_to_ingestion_trace():
    set_ingestion_trace_id("trace-abc")
    assert get_correlation_id() == "trace-abc"
