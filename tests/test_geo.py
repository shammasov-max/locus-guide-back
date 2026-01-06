import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_languages(client: AsyncClient):
    response = await client.get("/api/v1/geo/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert "default" in data
    assert data["default"] == "en"
    assert len(data["languages"]) > 0


@pytest.mark.asyncio
async def test_autocomplete_missing_query(client: AsyncClient):
    response = await client.get("/api/v1/geo/autocomplete")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_autocomplete_coords_validation(client: AsyncClient):
    # Only lat provided
    response = await client.get("/api/v1/geo/autocomplete?q=test&lat=50")
    assert response.status_code == 400

    # Only lon provided
    response = await client.get("/api/v1/geo/autocomplete?q=test&lon=30")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_cities_with_tours_empty(client: AsyncClient):
    response = await client.get("/api/v1/cities")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "cities" in data
    # No tours exist yet, so should be empty
    assert data["count"] == 0
