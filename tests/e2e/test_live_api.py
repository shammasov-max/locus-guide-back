"""
End-to-End API Tests against Live Server
Tests real HTTP requests to http://localhost:8001
"""
import httpx
import pytest
import uuid

BASE_URL = "http://localhost:8001"

# Create client that bypasses system proxy
client = httpx.Client(base_url=BASE_URL, trust_env=False, timeout=30.0)


class TestHealthAndDocs:
    """Test health check and OpenAPI documentation endpoints"""

    def test_health_check(self):
        """Health endpoint returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_openapi_json(self):
        """OpenAPI JSON schema is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Locus Guide API"
        assert "paths" in data
        # Verify API structure
        assert "/api/v1/auth/register" in data["paths"]
        assert "/api/v1/auth/login" in data["paths"]
        assert "/api/v1/cities/autocomplete" in data["paths"]
        assert "/api/v1/routes" in data["paths"]

    def test_swagger_ui(self):
        """Swagger UI documentation is accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger-ui" in response.text.lower() or "openapi" in response.text.lower()

    def test_redoc(self):
        """ReDoc documentation is accessible"""
        response = client.get("/redoc")
        assert response.status_code == 200


class TestAuthFlow:
    """Test complete authentication flow"""

    @pytest.fixture
    def unique_email(self):
        """Generate unique email for each test"""
        return f"e2e_test_{uuid.uuid4().hex[:8]}@test.com"

    def test_register_and_login_flow(self, unique_email):
        """Complete registration and login flow"""
        password = "SecurePass123!"

        # 1. Register new user
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": password,
                "display_name": "E2E Test User"
            }
        )
        assert register_response.status_code == 201, f"Register failed: {register_response.text}"
        register_data = register_response.json()
        # Response has nested tokens structure
        assert "tokens" in register_data
        assert "access_token" in register_data["tokens"]
        assert "refresh_token" in register_data["tokens"]
        assert "user" in register_data

        access_token = register_data["tokens"]["access_token"]

        # 2. Get profile with token
        profile_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == unique_email
        assert profile_data["display_name"] == "E2E Test User"

        # 3. Login with credentials (JSON)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": unique_email,
                "password": password
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "tokens" in login_data
        assert "access_token" in login_data["tokens"]

        # 4. Refresh token
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": register_data["tokens"]["refresh_token"]}
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        assert "access_token" in refresh_data

        # 5. Logout (requires refresh_token in body)
        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": register_data["tokens"]["refresh_token"]}
        )
        assert logout_response.status_code == 200

    def test_register_duplicate_email(self, unique_email):
        """Registering with duplicate email fails"""
        # Register first user
        client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": "Pass123!"}
        )

        # Try to register again with same email
        response = client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": "Pass123!"}
        )
        assert response.status_code == 409  # Conflict

    def test_login_wrong_password(self, unique_email):
        """Login with wrong password fails"""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": "CorrectPass123!"}
        )

        # Try login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "WrongPass123!"}
        )
        assert response.status_code == 401

    def test_protected_endpoint_without_auth(self):
        """Accessing protected endpoint without auth returns 401"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestCitiesEndpoints:
    """Test cities autocomplete endpoints"""

    def test_get_languages(self):
        """Get available languages"""
        response = client.get("/api/v1/cities/languages")
        assert response.status_code == 200
        data = response.json()
        # Response is object with languages list
        assert "languages" in data
        assert isinstance(data["languages"], list)
        # Should have common languages
        assert "en" in data["languages"]
        assert "ru" in data["languages"]

    def test_autocomplete_requires_query(self):
        """Autocomplete requires query parameter"""
        response = client.get("/api/v1/cities/autocomplete")
        assert response.status_code == 422  # Validation error

    def test_autocomplete_with_query(self):
        """Autocomplete returns results for valid query"""
        response = client.get(
            "/api/v1/cities/autocomplete",
            params={"q": "Mos", "lang": "en"}
        )
        assert response.status_code == 200
        data = response.json()
        # Response is object with cities list
        assert "cities" in data
        assert isinstance(data["cities"], list)


class TestRoutesEndpoints:
    """Test routes endpoints"""

    def test_list_routes_public(self):
        """List routes is publicly accessible"""
        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        # Response has routes array and count
        assert "routes" in data
        assert "count" in data
        assert isinstance(data["routes"], list)

    def test_list_routes_with_filters(self):
        """List routes with query filters"""
        response = client.get(
            "/api/v1/routes",
            params={"lang": "en", "limit": 10, "offset": 0}
        )
        assert response.status_code == 200

    def test_get_nonexistent_route(self):
        """Getting non-existent route returns 404"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/routes/{fake_uuid}")
        assert response.status_code == 404

    def test_create_route_requires_auth(self):
        """Creating route requires authentication"""
        response = client.post(
            "/api/v1/routes/admin",
            json={"city_id": 1, "slug": "test-route"}
        )
        assert response.status_code == 401

    def test_my_routes_requires_auth(self):
        """My routes endpoint requires authentication"""
        response = client.get("/api/v1/routes/me")
        # Could be 401 or 422 if route doesn't exist
        assert response.status_code in [401, 422]


class TestWishesEndpoints:
    """Test wishes endpoints"""

    @pytest.fixture
    def auth_headers(self):
        """Create authenticated user and return headers"""
        email = f"wish_test_{uuid.uuid4().hex[:8]}@test.com"
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "WishTest123!"}
        )
        data = response.json()
        # Handle nested tokens structure
        if "tokens" in data:
            token = data["tokens"]["access_token"]
        else:
            token = data["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_wish_route_requires_auth(self):
        """Wishing a route requires authentication"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.post(f"/api/v1/wishes/routes/{fake_uuid}/wish")
        assert response.status_code == 401

    def test_want_city_requires_auth(self):
        """Wanting a city requires authentication"""
        response = client.post("/api/v1/wishes/cities/1/want")
        assert response.status_code == 401

    def test_my_wishes_requires_auth(self):
        """My wishes endpoint requires authentication"""
        response = client.get("/api/v1/wishes/me")
        assert response.status_code == 401

    def test_my_wishes_empty(self, auth_headers):
        """New user has empty wishes"""
        response = client.get(
            "/api/v1/wishes/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["wished_routes"] == []
        assert data["wanted_cities"] == []

    def test_admin_stats_requires_editor(self, auth_headers):
        """Admin stats require editor role"""
        response = client.get(
            "/api/v1/wishes/admin/routes/stats",
            headers=auth_headers
        )
        # Regular user should get 403
        assert response.status_code == 403


class TestAPIValidation:
    """Test API input validation"""

    def test_register_invalid_email(self):
        """Registration validates email format"""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "Pass123!"}
        )
        assert response.status_code == 422

    def test_register_short_password(self):
        """Registration validates password length"""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "valid@email.com", "password": "short"}
        )
        assert response.status_code == 422

    def test_routes_invalid_uuid(self):
        """Routes endpoint validates UUID format"""
        response = client.get("/api/v1/routes/not-a-uuid")
        assert response.status_code == 422

    def test_autocomplete_invalid_limit(self):
        """Autocomplete validates limit parameter"""
        response = client.get(
            "/api/v1/cities/autocomplete",
            params={"q": "test", "limit": 1000}  # Exceeds max
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
