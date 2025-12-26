"""Tests for cities autocomplete search functionality.

Tests verify:
- Prefix matching and case insensitivity
- Multilingual support (Russian, Cyrillic)
- Sorting by similarity → distance → population
- GeoIP integration
- Response structure
"""

import pytest
from fastapi.testclient import TestClient

from tests.cities.conftest import (
    MOSCOW_GEONAMEID,
    BERLIN_GEONAMEID,
    BERLIN_COORDS,
)


class TestBasicSearch:
    """Test basic search functionality."""

    def test_search_returns_matching_cities(self, client: TestClient, ensure_geonames_data):
        """Test prefix matching returns correct cities.

        US-001: User wants to see list of available cities.
        """
        response = client.get("/api/v1/cities/autocomplete?q=Mosc")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        geoname_ids = [city["geoname_id"] for city in data["cities"]]
        assert MOSCOW_GEONAMEID in geoname_ids

    def test_search_case_insensitive(self, client: TestClient, ensure_geonames_data):
        """Test case insensitive search.

        US-018: Usability should be seamless.
        """
        response_lower = client.get("/api/v1/cities/autocomplete?q=moscow")
        response_upper = client.get("/api/v1/cities/autocomplete?q=MOSCOW")

        ids_lower = {c["geoname_id"] for c in response_lower.json()["cities"]}
        ids_upper = {c["geoname_id"] for c in response_upper.json()["cities"]}

        assert MOSCOW_GEONAMEID in ids_lower
        assert MOSCOW_GEONAMEID in ids_upper


class TestLanguageSupport:
    """Test multilingual search and display."""

    def test_local_name_in_russian(self, client: TestClient, ensure_geonames_data):
        """Test lang=ru returns Russian local_name.

        US-010: User wants app in preferred language.
        """
        response = client.get("/api/v1/cities/autocomplete?q=Moscow&lang=ru")

        assert response.status_code == 200
        moscow = next(
            (c for c in response.json()["cities"] if c["geoname_id"] == MOSCOW_GEONAMEID),
            None
        )
        assert moscow is not None
        assert moscow["local_name"] == "Москва"

    def test_search_by_cyrillic(self, client: TestClient, ensure_geonames_data):
        """Test searching with Cyrillic characters.

        US-009/010: App should work with Cyrillic keyboard.
        """
        response = client.get("/api/v1/cities/autocomplete?q=Моск&lang=ru")

        assert response.status_code == 200
        local_names = [c["local_name"] for c in response.json()["cities"]]
        assert "Москва" in local_names


class TestSorting:
    """Test sorting by similarity → distance → population."""

    def test_similarity_priority(self, client: TestClient, ensure_geonames_data):
        """Test exact match ranks higher due to pg_trgm similarity."""
        response = client.get("/api/v1/cities/autocomplete?q=Berlin&limit=10")

        assert response.status_code == 200
        first_city = response.json()["cities"][0]
        assert first_city["name"] == "Berlin"

    def test_distance_priority_over_population(self, client: TestClient, ensure_geonames_data):
        """Test nearby cities rank higher than distant large cities."""
        berlin_lat, berlin_lon = BERLIN_COORDS

        response = client.get(
            f"/api/v1/cities/autocomplete?q=M&lat={berlin_lat}&lon={berlin_lon}&limit=20"
        )

        cities = response.json()["cities"]
        distances = [c["distance_km"] for c in cities if c["distance_km"] is not None]

        if len(distances) >= 2:
            assert distances[0] <= distances[-1]

    def test_nearest_city_first(self, client: TestClient, ensure_geonames_data):
        """Test searching from Berlin returns Berlin as closest.

        US-002: App should show nearby routes.
        """
        berlin_lat, berlin_lon = BERLIN_COORDS

        response = client.get(
            f"/api/v1/cities/autocomplete?q=Berlin&lat={berlin_lat}&lon={berlin_lon}&limit=5"
        )

        berlin = next(
            (c for c in response.json()["cities"] if c["geoname_id"] == BERLIN_GEONAMEID),
            None
        )
        assert berlin is not None
        assert berlin["distance_km"] < 1


class TestDistanceCalculation:
    """Test distance-related functionality."""

    def test_user_location_in_response(self, client: TestClient, ensure_geonames_data):
        """Test user_location included when coordinates provided."""
        response = client.get("/api/v1/cities/autocomplete?q=M&lat=55.75&lon=37.61")

        data = response.json()
        assert data["user_location"] is not None
        assert data["user_location"]["lat"] == 55.75

    def test_no_distance_without_coords(self, client: TestClient, ensure_geonames_data):
        """Test distance_km is null without coordinates."""
        response = client.get("/api/v1/cities/autocomplete?q=Moscow")

        data = response.json()
        assert data["user_location"] is None
        for city in data["cities"]:
            assert city["distance_km"] is None


class TestGeoIPIntegration:
    """Test GeoIP fallback for coordinates."""

    @pytest.mark.integration
    def test_geoip_with_real_ip(self, client: TestClient, ensure_geonames_data):
        """Test GeoIP determines coordinates for public IP.

        US-002: App should auto-detect user location.
        """
        response = client.get(
            "/api/v1/cities/autocomplete?q=M",
            headers={"X-Forwarded-For": "8.8.8.8"}
        )

        data = response.json()
        assert data["user_location"] is not None


class TestResponseStructure:
    """Test response structure and field completeness."""

    def test_city_contains_required_fields(self, client: TestClient, ensure_geonames_data):
        """Test each city contains all required fields."""
        response = client.get("/api/v1/cities/autocomplete?q=Moscow")

        data = response.json()
        if data["count"] > 0:
            city = data["cities"][0]
            required_fields = [
                "geoname_id", "name", "local_name", "country_code",
                "country_name", "population", "lat", "lon", "distance_km",
            ]
            for field in required_fields:
                assert field in city

    def test_country_name_populated(self, client: TestClient, ensure_geonames_data):
        """Test country_name populated from countries table."""
        response = client.get("/api/v1/cities/autocomplete?q=Moscow")

        moscow = next(
            (c for c in response.json()["cities"] if c["geoname_id"] == MOSCOW_GEONAMEID),
            None
        )
        assert moscow["country_name"] == "Russia"
        assert moscow["country_code"] == "RU"
