"""Tests for cities autocomplete API."""
from fastapi.testclient import TestClient


def test_get_languages(client: TestClient):
    """Test languages endpoint."""
    response = client.get("/api/v1/cities/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert "en" in data["languages"]
    assert "ru" in data["languages"]
    assert "de" in data["languages"]


def test_autocomplete_missing_query(client: TestClient):
    """Test autocomplete without query parameter."""
    response = client.get("/api/v1/cities/autocomplete")
    assert response.status_code == 422  # Validation error


def test_autocomplete_invalid_language(client: TestClient):
    """Test autocomplete with unsupported language."""
    response = client.get("/api/v1/cities/autocomplete?q=Moscow&lang=xx")
    assert response.status_code == 400


def test_autocomplete_invalid_limit(client: TestClient):
    """Test autocomplete with invalid limit."""
    response = client.get("/api/v1/cities/autocomplete?q=Moscow&limit=100")
    assert response.status_code == 422  # Exceeds max_limit


def test_autocomplete_invalid_coordinates(client: TestClient):
    """Test autocomplete with invalid coordinates."""
    response = client.get("/api/v1/cities/autocomplete?q=Moscow&lat=200&lon=50")
    assert response.status_code == 422  # lat out of range


def test_autocomplete_empty_result(client: TestClient):
    """Test autocomplete with query that returns no results."""
    response = client.get("/api/v1/cities/autocomplete?q=xyznonexistent123")
    assert response.status_code == 200
    data = response.json()
    assert data["cities"] == []
    assert data["query"] == "xyznonexistent123"
