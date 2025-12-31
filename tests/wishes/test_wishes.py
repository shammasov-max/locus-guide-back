"""Tests for wishes API endpoints."""

import uuid
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.routes.models import (
    Tour, Route, Checkpoint,
    TourStatus, RouteStatus
)
from app.cities.models import City, Country
from app.auth.models import AppUser
from app.wishes.models import WishedRoute, WantedCity


def create_test_country(db_session, iso: str = "TC") -> Country:
    """Helper to create a test country."""
    country = db_session.get(Country, iso)
    if not country:
        country = Country(iso=iso, name=f"Test Country {iso}")
        db_session.add(country)
        db_session.flush()
    return country


def create_test_city(db_session, geonameid: int, name: str = "Test City") -> City:
    """Helper to create a test city with required FK."""
    country = create_test_country(db_session)
    city = City(
        geonameid=geonameid,
        name=name,
        country_code=country.iso,
        geom=from_shape(Point(0, 0), srid=4326)
    )
    db_session.add(city)
    db_session.flush()
    return city


def create_test_user(db_session, user_id: int = 1) -> AppUser:
    """Helper to create a test user."""
    from sqlalchemy import select
    stmt = select(AppUser).where(AppUser.id == user_id)
    user = db_session.execute(stmt).scalar_one_or_none()
    if user:
        return user

    user = AppUser(
        id=user_id,
        email=f"testuser{user_id}@example.com",
        role="user"
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_coming_soon_tour(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Coming Soon Tour"
) -> tuple[Tour, Route]:
    """Helper to create a coming_soon tour."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

    tour = Tour(
        city_id=city.geonameid,
        slug=slug,
        status=TourStatus.COMING_SOON,
        created_by_user_id=user.id
    )
    db_session.add(tour)
    db_session.flush()

    route = Route(
        tour_id=tour.id,
        version_no=1,
        status=RouteStatus.DRAFT,
        title_i18n={"en": title_en},
        languages=["en"],
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.commit()
    return tour, route


def create_published_tour(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Published Tour"
) -> tuple[Tour, Route]:
    """Helper to create a published tour."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

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
        title_i18n={"en": title_en},
        languages=["en"],
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.flush()

    tour.published_route_id = route.id
    db_session.commit()
    return tour, route


class TestWishTour:
    """Test wishing tours."""

    def test_wish_tour_requires_auth(self, client):
        """Test that wishing a tour requires authentication."""
        fake_id = uuid.uuid4()
        response = client.post(f"/api/v1/wishes/routes/{fake_id}/wish")
        assert response.status_code == 401

    def test_wish_coming_soon_tour(self, client, db_session, auth_headers):
        """Test wishing a coming_soon tour succeeds."""
        tour, _ = create_coming_soon_tour(
            db_session, city_geonameid=100, slug="wish-test", title_en="Wishable Tour"
        )

        response = client.post(
            f"/api/v1/wishes/routes/{tour.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tour_id"] == str(tour.id)
        assert data["is_active"] is True

    def test_cannot_wish_published_tour(self, client, db_session, auth_headers):
        """Test that wishing a published tour fails."""
        tour, _ = create_published_tour(
            db_session, city_geonameid=101, slug="published-tour", title_en="Published Tour"
        )

        response = client.post(
            f"/api/v1/wishes/routes/{tour.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "coming_soon" in response.json()["detail"].lower()

    def test_wish_nonexistent_tour(self, client, auth_headers):
        """Test wishing a non-existent tour returns 404."""
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/v1/wishes/routes/{fake_id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_unwish_tour(self, client, db_session, auth_headers):
        """Test unwishing a tour."""
        tour, _ = create_coming_soon_tour(
            db_session, city_geonameid=102, slug="unwish-test", title_en="Unwishable Tour"
        )

        # First wish it
        client.post(f"/api/v1/wishes/routes/{tour.id}/wish", headers=auth_headers)

        # Then unwish it
        response = client.delete(
            f"/api/v1/wishes/routes/{tour.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_rewish_tour(self, client, db_session, auth_headers):
        """Test that re-wishing a tour reactivates it."""
        tour, _ = create_coming_soon_tour(
            db_session, city_geonameid=103, slug="rewish-test", title_en="Rewishable Tour"
        )

        # Wish, unwish, then rewish
        client.post(f"/api/v1/wishes/routes/{tour.id}/wish", headers=auth_headers)
        client.delete(f"/api/v1/wishes/routes/{tour.id}/wish", headers=auth_headers)

        response = client.post(
            f"/api/v1/wishes/routes/{tour.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["is_active"] is True


class TestWantCity:
    """Test wanting cities."""

    def test_want_city_requires_auth(self, client):
        """Test that wanting a city requires authentication."""
        response = client.post("/api/v1/wishes/cities/12345/want")
        assert response.status_code == 401

    def test_want_city_success(self, client, db_session, auth_headers):
        """Test wanting a city succeeds."""
        city = create_test_city(db_session, geonameid=200, name="Wanted City")
        db_session.commit()

        response = client.post(
            f"/api/v1/wishes/cities/{city.geonameid}/want",
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["geonameid"] == city.geonameid
        assert data["is_active"] is True
        assert data["has_routes"] is False

    def test_want_nonexistent_city(self, client, auth_headers):
        """Test wanting a non-existent city returns 404."""
        response = client.post(
            "/api/v1/wishes/cities/999999999/want",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_unwant_city(self, client, db_session, auth_headers):
        """Test unwanting a city."""
        city = create_test_city(db_session, geonameid=201, name="Unwanted City")
        db_session.commit()

        # First want it
        client.post(f"/api/v1/wishes/cities/{city.geonameid}/want", headers=auth_headers)

        # Then unwant it
        response = client.delete(
            f"/api/v1/wishes/cities/{city.geonameid}/want",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_city_has_routes_updates(self, client, db_session, auth_headers):
        """Test that has_routes field updates when tours are added."""
        city = create_test_city(db_session, geonameid=202, name="City With Tours")
        db_session.commit()

        # Want city (no tours yet)
        response = client.post(
            f"/api/v1/wishes/cities/{city.geonameid}/want",
            headers=auth_headers
        )
        assert response.json()["has_routes"] is False

        # Add a published tour to the city
        user = create_test_user(db_session, user_id=999)
        tour = Tour(
            city_id=city.geonameid,
            slug="new-tour",
            status=TourStatus.PUBLISHED,
            created_by_user_id=user.id
        )
        db_session.add(tour)
        db_session.flush()
        route = Route(
            tour_id=tour.id,
            version_no=1,
            status=RouteStatus.PUBLISHED,
            title_i18n={"en": "New Tour"},
            languages=["en"],
            created_by_user_id=user.id
        )
        db_session.add(route)
        tour.published_route_id = route.id
        db_session.commit()

        # Check that has_routes is now True
        response = client.get(
            f"/api/v1/wishes/cities/{city.geonameid}/want",
            headers=auth_headers
        )
        assert response.json()["has_routes"] is True


class TestMyWishes:
    """Test user's wishes endpoint."""

    def test_my_wishes_requires_auth(self, client):
        """Test that my wishes endpoint requires authentication."""
        response = client.get("/api/v1/wishes/me")
        assert response.status_code == 401

    def test_my_wishes_empty(self, client, auth_headers):
        """Test my wishes when user has no wishes."""
        response = client.get("/api/v1/wishes/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["wished_routes"] == []
        assert data["wanted_cities"] == []

    def test_my_wishes_with_data(self, client, db_session, auth_headers):
        """Test my wishes with both wished tours and wanted cities."""
        # Create and wish a tour
        tour, _ = create_coming_soon_tour(
            db_session, city_geonameid=300, slug="my-tour", title_en="My Wished Tour"
        )
        client.post(f"/api/v1/wishes/routes/{tour.id}/wish", headers=auth_headers)

        # Create and want a city
        city = create_test_city(db_session, geonameid=301, name="My Wanted City")
        db_session.commit()
        client.post(f"/api/v1/wishes/cities/{city.geonameid}/want", headers=auth_headers)

        # Get my wishes
        response = client.get("/api/v1/wishes/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["wished_routes"]) == 1
        assert len(data["wanted_cities"]) == 1


class TestAdminWishStats:
    """Test admin analytics endpoints."""

    def test_tour_stats_requires_editor(self, client, auth_headers):
        """Test that tour wish stats requires editor role."""
        response = client.get(
            "/api/v1/wishes/admin/routes/stats",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_tour_stats_empty(self, client, editor_headers):
        """Test tour wish stats with no wishes."""
        response = client.get(
            "/api/v1/wishes/admin/routes/stats",
            headers=editor_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["routes"] == []

    def test_city_stats_requires_editor(self, client, auth_headers):
        """Test that city want stats requires editor role."""
        response = client.get(
            "/api/v1/wishes/admin/cities/stats",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_city_stats_empty(self, client, editor_headers):
        """Test city want stats with no wants."""
        response = client.get(
            "/api/v1/wishes/admin/cities/stats",
            headers=editor_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["cities"] == []


class TestRoutesListIntegration:
    """Test is_wished field in routes list."""

    def test_routes_list_includes_is_wished(self, client, db_session, auth_headers):
        """Test that routes list includes is_wished field when authenticated."""
        # Create a published tour
        tour, route = create_published_tour(
            db_session, city_geonameid=400, slug="wished-tour", title_en="Tour to Wish"
        )

        # List routes - is_wished should be False
        response = client.get("/api/v1/routes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["routes"][0]["is_wished"] is False

    def test_routes_list_no_is_wished_without_auth(self, client, db_session):
        """Test that routes list without auth has is_wished as False."""
        tour, route = create_published_tour(
            db_session, city_geonameid=401, slug="anon-tour", title_en="Anonymous Tour"
        )

        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["routes"][0]["is_wished"] is False
