import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_metrics(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "feedstream_http_requests_total" in body
    assert "feedstream_query_latency_seconds" in body


@pytest.mark.asyncio
async def test_request_id_response_header_exists(client: AsyncClient):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
