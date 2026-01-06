import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tours_empty(client: AsyncClient):
    response = await client.get("/api/v1/tours")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["tours"] == []


@pytest.mark.asyncio
async def test_get_tour_not_found(client: AsyncClient):
    response = await client.get("/api/v1/tours/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_bundles_empty(client: AsyncClient):
    response = await client.get("/api/v1/bundles")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_get_bundle_not_found(client: AsyncClient):
    response = await client.get("/api/v1/bundles/999")
    assert response.status_code == 404


# Runs tests
@pytest.mark.asyncio
async def test_list_runs_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/me/runs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/me/runs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


# User lists tests
@pytest.mark.asyncio
async def test_await_list_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/me/await-list")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_await_list_empty(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/me/await-list", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_watch_list_empty(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/me/watch-list", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_entitlements_empty(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/me/entitlements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


# Editor tests
@pytest.mark.asyncio
async def test_editor_tours_unauthorized(client: AsyncClient, auth_headers: dict):
    # Regular user shouldn't access editor routes
    response = await client.get("/api/v1/editor/tours", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_editor_list_tours(client: AsyncClient, editor_headers: dict):
    response = await client.get("/api/v1/editor/tours", headers=editor_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


# Admin tests
@pytest.mark.asyncio
async def test_admin_unauthorized(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/editors", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_unauthorized_editor(client: AsyncClient, editor_headers: dict):
    response = await client.get("/api/v1/admin/editors", headers=editor_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_editors(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/v1/admin/editors", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "editors" in data


@pytest.mark.asyncio
async def test_admin_list_bundles(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/v1/admin/bundles", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
