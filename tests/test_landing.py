import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_landing_page(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "feedstream" in response.text
    assert "/healthz" in response.text
