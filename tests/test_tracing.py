import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_request_id_propagates_from_input_header(client: AsyncClient):
    request_id = "req-test-123"
    response = await client.get("/healthz", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
