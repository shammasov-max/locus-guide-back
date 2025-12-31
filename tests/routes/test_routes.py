"""Tests for routes API endpoints."""

import uuid
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.routes.models import (
    Tour, Route, Checkpoint,
    TourStatus, RouteStatus
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
    """Helper to create a test user for tour creation."""
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


def create_published_tour(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Test Tour",
    title_ru: str = None,
    summary_en: str = None,
    checkpoint_location: Point = None
) -> tuple[Tour, Route, Checkpoint | None]:
    """Helper to create a published tour with optional checkpoint."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

    title_i18n = {"en": title_en}
    if title_ru:
        title_i18n["ru"] = title_ru

    tour = Tour(
        city_id=city.geonameid,
        slug=slug,
        status=TourStatus.PUBLISHED,
        created_by_user_id=user.id
    )
    db_session.add(tour)
    db_session.flush()

    route = Route(
        tour_id=tour.id,
        version_no=1,
        status=RouteStatus.PUBLISHED,
        title_i18n=title_i18n,
        summary_i18n={"en": summary_en} if summary_en else None,
        languages=list(title_i18n.keys()),
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.flush()

    tour.published_route_id = route.id

    checkpoint = None
    if checkpoint_location:
        checkpoint = Checkpoint(
            route_id=route.id,
            seq_no=0,
            title_i18n={"en": "First Checkpoint"},
            location=from_shape(checkpoint_location, srid=4326),
            is_visible=True
        )
        db_session.add(checkpoint)

    db_session.commit()
    return tour, route, checkpoint


class TestPublicRoutes:
    """Test public routes endpoints (no auth required)."""

    def test_list_routes_empty(self, client):
        """Test listing routes when none exist."""
        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["routes"] == []

    def test_list_routes_with_published_tour(self, client, db_session):
        """Test listing routes with a published tour."""
        create_published_tour(db_session, city_geonameid=1, slug="test-tour", title_en="Test Tour")

        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["routes"][0]["slug"] == "test-tour"

    def test_list_routes_with_language(self, client, db_session):
        """Test listing routes with different languages."""
        create_published_tour(
            db_session, city_geonameid=2, slug="i18n-tour",
            title_en="English Title", title_ru="Русский заголовок"
        )

        response = client.get("/api/v1/routes?lang=en")
        assert response.status_code == 200
        assert response.json()["routes"][0]["title"] == "English Title"

        response = client.get("/api/v1/routes?lang=ru")
        assert response.status_code == 200
        assert response.json()["routes"][0]["title"] == "Русский заголовок"

    def test_get_tour_not_found(self, client):
        """Test getting a non-existent tour."""
        fake_id = uuid.uuid4()
        response = client.get(f"/api/v1/routes/{fake_id}")
        assert response.status_code == 404


class TestTourSearch:
    """Test tour search functionality."""

    def test_search_by_title(self, client, db_session):
        """Test searching tours by title."""
        create_published_tour(db_session, city_geonameid=10, slug="historic-walk", title_en="Historic Downtown Walk")

        response = client.get("/api/v1/routes?search=Historic")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert "Historic" in data["routes"][0]["title"]

    def test_search_by_summary(self, client, db_session):
        """Test searching tours by summary."""
        create_published_tour(
            db_session, city_geonameid=11, slug="art-tour",
            title_en="Art Tour", summary_en="Discover magnificent sculptures and paintings"
        )

        response = client.get("/api/v1/routes?search=sculptures")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_search_case_insensitive(self, client, db_session):
        """Test that search is case insensitive."""
        create_published_tour(db_session, city_geonameid=12, slug="castle-tour", title_en="CASTLE TOUR")

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
    """Test nearby tours filter using PostGIS."""

    def test_nearby_tours(self, client, db_session):
        """Test filtering tours by proximity."""
        # Create tour with checkpoint at Times Square
        create_published_tour(
            db_session, city_geonameid=20, slug="nearby-tour",
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

    def test_create_tour_requires_auth(self, client, db_session):
        """Test that creating a tour requires authentication."""
        city = create_test_city(db_session, geonameid=50, name="Auth City")
        db_session.commit()
        tour_data = {"city_id": city.geonameid, "slug": "test-tour", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=tour_data)
        assert response.status_code == 401

    def test_create_tour_forbidden_for_regular_user(self, client, db_session, auth_headers):
        """Test that regular users cannot create tours."""
        city = create_test_city(db_session, geonameid=51, name="Regular City")
        db_session.commit()
        tour_data = {"city_id": city.geonameid, "slug": "user-tour", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=tour_data, headers=auth_headers)
        assert response.status_code == 403

    def test_create_tour_allowed_for_editor(self, client, db_session, editor_headers):
        """Test that editors can create tours."""
        city = create_test_city(db_session, geonameid=52, name="Editor City")
        db_session.commit()
        tour_data = {"city_id": city.geonameid, "slug": "editor-tour", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=tour_data, headers=editor_headers)
        assert response.status_code == 201

    def test_create_tour_allowed_for_admin(self, client, db_session, admin_headers):
        """Test that admins can create tours."""
        city = create_test_city(db_session, geonameid=53, name="Admin City")
        db_session.commit()
        tour_data = {"city_id": city.geonameid, "slug": "admin-tour", "status": "draft"}
        response = client.post("/api/v1/routes/admin", json=tour_data, headers=admin_headers)
        assert response.status_code == 201

    def test_create_tour_requires_editor(self, client, db_session, auth_headers, editor_headers):
        """Test that creating tours requires editor role."""
        city = create_test_city(db_session, geonameid=40, name="RBAC City")
        db_session.commit()

        tour_data = {"city_id": city.geonameid, "slug": "new-tour", "status": "draft"}

        # Regular user - forbidden
        response = client.post("/api/v1/routes/admin", json=tour_data, headers=auth_headers)
        assert response.status_code == 403

        # Editor - allowed
        response = client.post("/api/v1/routes/admin", json=tour_data, headers=editor_headers)
        assert response.status_code == 201


class TestUserProgress:
    """Test user progress tracking endpoints."""

    def test_start_tour_requires_auth(self, client):
        """Test that starting a tour requires authentication."""
        fake_id = uuid.uuid4()
        response = client.post(f"/api/v1/routes/{fake_id}/start")
        assert response.status_code == 401

    def test_start_tour(self, client, db_session, auth_headers):
        """Test starting a tour creates session."""
        tour, route, _ = create_published_tour(
            db_session, city_geonameid=30, slug="start-tour", title_en="Start Tour"
        )

        response = client.post(f"/api/v1/routes/{tour.id}/start", headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["locked_route_id"] == str(route.id)
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
