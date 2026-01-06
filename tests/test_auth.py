import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "display_name": "New User",
            "units": "metric",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert "tokens" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["display_name"] == "New User"
    assert data["user"]["units"] == "metric"
    assert data["user"]["role"] == "user"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "password123",
        },
    )
    # Second registration with same email
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "password456",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123",
        },
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "tokens" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "correctpassword",
        },
    )
    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, auth_headers: dict):
    response = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "display_name": "Updated Name",
            "units": "imperial",
            "ui_lang": "ru",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Name"
    assert data["units"] == "imperial"
    assert data["ui_lang"] == "ru"


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    # Register to get tokens
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "password123",
        },
    )
    refresh_token = reg_response.json()["tokens"]["refresh_token"]

    # Refresh tokens
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    # Register
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@example.com",
            "password": "password123",
        },
    )
    tokens = reg_response.json()["tokens"]

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200

    # Try to use the revoked refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_all(client: AsyncClient):
    # Register
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logoutall@example.com",
            "password": "password123",
        },
    )
    tokens = reg_response.json()["tokens"]

    # Logout all
    response = await client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_request(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset@example.com",
            "password": "password123",
        },
    )

    # Request password reset
    response = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "reset@example.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_request_nonexistent_email(client: AsyncClient):
    # Should still return 200 to prevent email enumeration
    response = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    # Register
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "delete@example.com",
            "password": "password123",
        },
    )
    tokens = reg_response.json()["tokens"]

    # Delete account
    response = await client.delete(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200

    # Try to login again
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "delete@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 401
