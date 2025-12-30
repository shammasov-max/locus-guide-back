"""Tests for wishes API endpoints."""

import uuid
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.routes.models import (
    Trip, Route, Checkpoint,
    TripStatus, RouteStatus
)
from app.cities.models import City, Country
from app.auth.models import AppUser
from app.wishes.models import WishedTrip, WantedCity


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


def create_coming_soon_trip(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Coming Soon Trip"
) -> tuple[Trip, Route]:
    """Helper to create a coming_soon trip."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

    trip = Trip(
        city_id=city.geonameid,
        slug=slug,
        status=TripStatus.COMING_SOON,
        created_by_user_id=user.id
    )
    db_session.add(trip)
    db_session.flush()

    route = Route(
        trip_id=trip.id,
        version_no=1,
        status=RouteStatus.DRAFT,
        title_i18n={"en": title_en},
        languages=["en"],
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.commit()
    return trip, route


def create_published_trip(
    db_session,
    city_geonameid: int,
    slug: str,
    title_en: str = "Published Trip"
) -> tuple[Trip, Route]:
    """Helper to create a published trip."""
    city = create_test_city(db_session, geonameid=city_geonameid, name=f"City {city_geonameid}")
    user = create_test_user(db_session)

    trip = Trip(
        city_id=city.geonameid,
        slug=slug,
        status=TripStatus.PUBLISHED,
        created_by_user_id=user.id
    )
    db_session.add(trip)
    db_session.flush()

    route = Route(
        trip_id=trip.id,
        version_no=1,
        status=RouteStatus.PUBLISHED,
        title_i18n={"en": title_en},
        languages=["en"],
        created_by_user_id=user.id
    )
    db_session.add(route)
    db_session.flush()

    trip.published_route_id = route.id
    db_session.commit()
    return trip, route


class TestWishTrip:
    """Test wishing trips."""

    def test_wish_trip_requires_auth(self, client):
        """Test that wishing a trip requires authentication."""
        fake_id = uuid.uuid4()
        response = client.post(f"/api/v1/wishes/routes/{fake_id}/wish")
        assert response.status_code == 401

    def test_wish_coming_soon_trip(self, client, db_session, auth_headers):
        """Test wishing a coming_soon trip succeeds."""
        trip, _ = create_coming_soon_trip(
            db_session, city_geonameid=100, slug="wish-test", title_en="Wishable Trip"
        )

        response = client.post(
            f"/api/v1/wishes/routes/{trip.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["trip_id"] == str(trip.id)
        assert data["is_active"] is True

    def test_cannot_wish_published_trip(self, client, db_session, auth_headers):
        """Test that wishing a published trip fails."""
        trip, _ = create_published_trip(
            db_session, city_geonameid=101, slug="published-trip", title_en="Published Trip"
        )

        response = client.post(
            f"/api/v1/wishes/routes/{trip.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "coming_soon" in response.json()["detail"].lower()

    def test_wish_nonexistent_trip(self, client, auth_headers):
        """Test wishing a non-existent trip returns 404."""
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/v1/wishes/routes/{fake_id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_unwish_trip(self, client, db_session, auth_headers):
        """Test unwishing a trip."""
        trip, _ = create_coming_soon_trip(
            db_session, city_geonameid=102, slug="unwish-test", title_en="Unwishable Trip"
        )

        # First wish it
        client.post(f"/api/v1/wishes/routes/{trip.id}/wish", headers=auth_headers)

        # Then unwish it
        response = client.delete(
            f"/api/v1/wishes/routes/{trip.id}/wish",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_rewish_trip(self, client, db_session, auth_headers):
        """Test that re-wishing a trip reactivates it."""
        trip, _ = create_coming_soon_trip(
            db_session, city_geonameid=103, slug="rewish-test", title_en="Rewishable Trip"
        )

        # Wish, unwish, then rewish
        client.post(f"/api/v1/wishes/routes/{trip.id}/wish", headers=auth_headers)
        client.delete(f"/api/v1/wishes/routes/{trip.id}/wish", headers=auth_headers)

        response = client.post(
            f"/api/v1/wishes/routes/{trip.id}/wish",
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
        """Test that has_routes field updates when trips are added."""
        city = create_test_city(db_session, geonameid=202, name="City With Trips")
        db_session.commit()

        # Want city (no trips yet)
        response = client.post(
            f"/api/v1/wishes/cities/{city.geonameid}/want",
            headers=auth_headers
        )
        assert response.json()["has_routes"] is False

        # Add a published trip to the city
        user = create_test_user(db_session, user_id=999)
        trip = Trip(
            city_id=city.geonameid,
            slug="new-trip",
            status=TripStatus.PUBLISHED,
            created_by_user_id=user.id
        )
        db_session.add(trip)
        db_session.flush()
        route = Route(
            trip_id=trip.id,
            version_no=1,
            status=RouteStatus.PUBLISHED,
            title_i18n={"en": "New Trip"},
            languages=["en"],
            created_by_user_id=user.id
        )
        db_session.add(route)
        trip.published_route_id = route.id
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
        """Test my wishes with both wished trips and wanted cities."""
        # Create and wish a trip
        trip, _ = create_coming_soon_trip(
            db_session, city_geonameid=300, slug="my-trip", title_en="My Wished Trip"
        )
        client.post(f"/api/v1/wishes/routes/{trip.id}/wish", headers=auth_headers)

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

    def test_trip_stats_requires_editor(self, client, auth_headers):
        """Test that trip wish stats requires editor role."""
        response = client.get(
            "/api/v1/wishes/admin/routes/stats",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_trip_stats_empty(self, client, editor_headers):
        """Test trip wish stats with no wishes."""
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
        # Create a published trip
        trip, route = create_published_trip(
            db_session, city_geonameid=400, slug="wished-trip", title_en="Trip to Wish"
        )

        # List routes - is_wished should be False
        response = client.get("/api/v1/routes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["routes"][0]["is_wished"] is False

    def test_routes_list_no_is_wished_without_auth(self, client, db_session):
        """Test that routes list without auth has is_wished as False."""
        trip, route = create_published_trip(
            db_session, city_geonameid=401, slug="anon-trip", title_en="Anonymous Trip"
        )

        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["routes"][0]["is_wished"] is False
