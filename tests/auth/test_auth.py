class TestRegistration:
    def test_register_success(self, client, test_user_data):
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 201

        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["display_name"] == test_user_data["display_name"]
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    def test_register_duplicate_email(self, client, test_user_data, registered_user):
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 409

    def test_register_invalid_email(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "securepassword123",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client, test_user_data, registered_user):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == test_user_data["email"]

    def test_login_wrong_password(self, client, test_user_data, registered_user):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


class TestRefreshToken:
    def test_refresh_success(self, client, registered_user):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestProfile:
    def test_get_me(self, client, auth_headers, test_user_data):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["display_name"] == test_user_data["display_name"]

    def test_get_me_unauthorized(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401  # No auth header

    def test_update_profile(self, client, auth_headers):
        response = client.patch(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={
                "display_name": "Updated Name",
                "units": "imperial",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["units"] == "imperial"


class TestLogout:
    def test_logout_success(self, client, auth_headers, registered_user):
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert response.status_code == 200

        # Verify refresh token is invalidated
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert refresh_response.status_code == 401

    def test_logout_all(self, client, auth_headers, registered_user):
        response = client.post("/api/v1/auth/logout-all", headers=auth_headers)
        assert response.status_code == 200


class TestPasswordReset:
    def test_request_password_reset(self, client, registered_user, test_user_data):
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": test_user_data["email"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert "reset_token" in data  # In dev mode, token is returned

    def test_confirm_password_reset(self, client, registered_user, test_user_data):
        # Request reset token
        request_response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": test_user_data["email"]},
        )
        reset_token = request_response.json()["reset_token"]

        # Confirm reset
        new_password = "newpassword123"
        confirm_response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": reset_token,
                "new_password": new_password,
            },
        )
        assert confirm_response.status_code == 200

        # Login with new password
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": new_password,
            },
        )
        assert login_response.status_code == 200


class TestDeleteAccount:
    def test_delete_account(self, client, auth_headers, test_user_data):
        response = client.delete("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200

        # Verify user is deleted
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert login_response.status_code == 401
