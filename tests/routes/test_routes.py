"""Tests for routes API endpoints."""

import uuid
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.routes.models import (
    Route, RouteVersion, Checkpoint,
    RouteStatus, RouteVersionStatus
)
from app.cities.models import City, Country
from app.auth.models import AppUser


def create_test_city(db_session, geonameid: int, name: str = "Test City") -> City:
    """Helper to create a test city with required FK."""
    country_code = "TC"
    country = db_session.get(Country, country_code)
    if not country:
        country = Country(iso=country_code, name="Test Country")
        db_session.add(country)
        db_session.flush()

    city = City(
        geonameid=geonameid,
        name=name,
        country_code=country_code,
        geom=from_shape(Point(0, 0), srid=4326)
    )
    db_session.add(city)
    db_session.flush()
    return city


def create_test_user(db_session, user_id: int = 1) -> AppUser:
    """Helper to create a test user for route creation."""
    from sqlalchemy import select
    stmt = select(AppUser).where(AppUser.id == user_id)
    user = db_session.execute(stmt).scalar_one_or_none()
    if user:
        return user

    user = AppUser(
        id=user_id,
        email=f"test{user_id}@example.com",
        role="user"
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_published_route(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Test Route",
    title_ru: str = None,
    summary_en: str = None,
    checkpoint_location: Point = None
) -> tuple[Route, RouteVersion, Checkpoint | None]:
    """Helper to create a published route with optional checkpoint."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

    title_i18n = {"en": title_en}
    if title_ru:
        title_i18n["ru"] = title_ru

    route = Route(
        city_id=city.geonameid,
        slug=slug,
        status=RouteStatus.PUBLISHED,
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.flush()

    version = RouteVersion(
        route_id=route.id,
        version_no=1,
        status=RouteVersionStatus.PUBLISHED,
        title_i18n=title_i18n,
        summary_i18n={"en": summary_en} if summary_en else None,
        languages=list(title_i18n.keys()),
        created_by_user_id=user.id
    )
    db_session.add(version)
    db_session.flush()

    route.published_version_id = version.id

    checkpoint = None
    if checkpoint_location:
        checkpoint = Checkpoint(
            route_version_id=version.id,
            seq_no=0,
            title_i18n={"en": "First Checkpoint"},
            location=from_shape(checkpoint_location, srid=4326),
            is_visible=True
        )
        db_session.add(checkpoint)

    db_session.commit()
    return route, version, checkpoint


class TestPublicRoutes:
    """Test public routes endpoints (no auth required)."""

    def test_list_routes_empty(self, client):
        """Test listing routes when none exist."""
        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["routes"] == []

    def test_list_routes_with_published_route(self, client, db_session):
        """Test listing routes with a published route."""
        create_published_route(db_session, city_geonameid=1, slug="test-route", title_en="Test Route")

        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["routes"][0]["slug"] == "test-route"

    def test_list_routes_with_language(self, client, db_session):
        """Test listing routes with different languages."""
        create_published_route(
            db_session, city_geonameid=2, slug="i18n-route",
            title_en="English Title", title_ru="Русский заголовок"
        )

        response = client.get("/api/v1/routes?lang=en")
        assert response.status_code == 200
        assert response.json()["routes"][0]["title"] == "English Title"

        response = client.get("/api/v1/routes?lang=ru")
        assert response.status_code == 200
        assert response.json()["routes"][0]["title"] == "Русский заголовок"

    def test_get_route_not_found(self, client):
        """Test getting a non-existent route."""
        fake_id = uuid.uuid4()
        response = client.get(f"/api/v1/routes/{fake_id}")
        assert response.status_code == 404


class TestRouteSearch:
    """Test route search functionality."""

    def test_search_by_title(self, client, db_session):
        """Test searching routes by title."""
        create_published_route(db_session, city_geonameid=10, slug="historic-walk", title_en="Historic Downtown Walk")

        response = client.get("/api/v1/routes?search=Historic")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert "Historic" in data["routes"][0]["title"]

    def test_search_by_summary(self, client, db_session):
        """Test searching routes by summary."""
        create_published_route(
            db_session, city_geonameid=11, slug="art-tour",
            title_en="Art Tour", summary_en="Discover magnificent sculptures and paintings"
        )

        response = client.get("/api/v1/routes?search=sculptures")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_search_case_insensitive(self, client, db_session):
        """Test that search is case insensitive."""
        create_published_route(db_session, city_geonameid=12, slug="castle-tour", title_en="CASTLE TOUR")

        response = client.get("/api/v1/routes?search=castle")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_search_no_results(self, client):
        """Test search with no matching results."""
        response = client.get("/api/v1/routes?search=nonexistent123xyz")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_search_min_length(self, client):
        """Test that search requires minimum 2 characters."""
        response = client.get("/api/v1/routes?search=a")
        assert response.status_code == 422


class TestNearbyFilter:
    """Test nearby routes filter using PostGIS."""

    def test_nearby_routes(self, client, db_session):
        """Test filtering routes by proximity."""
        # Create route with checkpoint at Times Square
        create_published_route(
            db_session, city_geonameid=20, slug="nearby-route",
            title_en="NYC Walking Tour",
            checkpoint_location=Point(-73.9855, 40.7580)
        )

        # Search near Times Square (should find)
        response = client.get("/api/v1/routes?lat=40.758&lon=-73.985&nearby_km=1")
        assert response.status_code == 200
        assert response.json()["count"] == 1

        # Search far from Times Square (London - should not find)
        response = client.get("/api/v1/routes?lat=51.5074&lon=-0.1278&nearby_km=10")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestRBAC:
    """Test role-based access control for admin endpoints."""

    def test_create_route_requires_auth(self, client, db_session):
        """Test that creating a route requires authentication."""
        city = create_test_city(db_session, geonameid=50, name="Auth City")
        db_session.commit()
        route_data = {"city_id": city.geonameid, "slug": "test-route", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=route_data)
        assert response.status_code == 401

    def test_create_route_forbidden_for_regular_user(self, client, db_session, auth_headers):
        """Test that regular users cannot create routes."""
        city = create_test_city(db_session, geonameid=51, name="Regular City")
        db_session.commit()
        route_data = {"city_id": city.geonameid, "slug": "user-route", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=route_data, headers=auth_headers)
        assert response.status_code == 403

    def test_create_route_allowed_for_editor(self, client, db_session, editor_headers):
        """Test that editors can create routes."""
        city = create_test_city(db_session, geonameid=52, name="Editor City")
        db_session.commit()
        route_data = {"city_id": city.geonameid, "slug": "editor-route", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=route_data, headers=editor_headers)
        assert response.status_code == 201

    def test_create_route_allowed_for_admin(self, client, db_session, admin_headers):
        """Test that admins can create routes."""
        city = create_test_city(db_session, geonameid=53, name="Admin City")
        db_session.commit()
        route_data = {"city_id": city.geonameid, "slug": "admin-route", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=route_data, headers=admin_headers)
        assert response.status_code == 201

    def test_create_route_requires_editor(self, client, db_session, auth_headers, editor_headers):
        """Test that creating routes requires editor role."""
        city = create_test_city(db_session, geonameid=40, name="RBAC City")
        db_session.commit()

        route_data = {"city_id": city.geonameid, "slug": "new-route", "status": "draft"}

        # Regular user - forbidden
        response = client.post("/api/v1/routes/admin", json=route_data, headers=auth_headers)
        assert response.status_code == 403

        # Editor - allowed
        response = client.post("/api/v1/routes/admin", json=route_data, headers=editor_headers)
        assert response.status_code == 201


class TestUserProgress:
    """Test user progress tracking endpoints."""

    def test_start_route_requires_auth(self, client):
        """Test that starting a route requires authentication."""
        fake_id = uuid.uuid4()
        response = client.post(f"/api/v1/routes/{fake_id}/start")
        assert response.status_code == 401

    def test_start_route(self, client, db_session, auth_headers):
        """Test starting a route creates session."""
        route, version, _ = create_published_route(
            db_session, city_geonameid=30, slug="start-route", title_en="Start Route"
        )

        response = client.post(f"/api/v1/routes/{route.id}/start", headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["locked_version_id"] == str(version.id)
        assert data["completed_at"] is None


class TestMyRoutes:
    """Test user's active routes endpoint."""

    def test_my_routes_requires_auth(self, client):
        """Test that my routes endpoint requires authentication."""
        response = client.get("/api/v1/routes/me/routes")
        assert response.status_code == 401

    def test_my_routes_empty(self, client, auth_headers):
        """Test my routes when user has no active routes."""
        response = client.get("/api/v1/routes/me/routes", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
