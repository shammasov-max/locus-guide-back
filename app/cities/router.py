from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.config import get_settings
from app.cities.schemas import AutocompleteResponse, UserLocation
from app.cities.service import CitySearchService
from app.cities.geoip import geoip_service

router = APIRouter()
settings = get_settings()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header first (for reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client
    if request.client:
        return request.client.host

    return ""


@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    summary="City Autocomplete Search",
    description="""
    Search for cities by name prefix with multilingual support.

    Results are sorted by:
    1. Distance from user (if coordinates provided)
    2. Population (descending)

    Coordinates can be:
    - Explicitly provided via `lat` and `lon` parameters
    - Automatically detected via GeoIP (if not provided)
    """,
)
def autocomplete(
    request: Request,
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search query (city name prefix)",
        examples=["Mosc", "Берл", "New Y"],
    ),
    lang: str = Query(
        default="en",
        description="Language for city names",
        examples=["en", "ru", "de"],
    ),
    lat: Optional[float] = Query(
        default=None,
        ge=-90,
        le=90,
        description="User latitude for distance sorting",
    ),
    lon: Optional[float] = Query(
        default=None,
        ge=-180,
        le=180,
        description="User longitude for distance sorting",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results",
    ),
    db: Session = Depends(get_db),
) -> AutocompleteResponse:
    """
    Search cities by name prefix with optional distance-based sorting.
    """
    # Validate language
    if lang not in settings.cities_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported: {', '.join(settings.cities_languages)}"
        )

    # Get user coordinates
    user_lat = lat
    user_lon = lon
    user_location = None

    # If coordinates not provided, try GeoIP
    if user_lat is None or user_lon is None:
        client_ip = get_client_ip(request)
        if client_ip:
            geoip_coords = geoip_service.get_coordinates(client_ip)
            if geoip_coords:
                user_lat, user_lon = geoip_coords

    if user_lat is not None and user_lon is not None:
        user_location = UserLocation(lat=user_lat, lon=user_lon)

    # Perform search
    search_service = CitySearchService(db)
    cities = search_service.search(
        query=q,
        lang=lang,
        lat=user_lat,
        lon=user_lon,
        limit=limit,
    )

    return AutocompleteResponse(
        query=q,
        lang=lang,
        user_location=user_location,
        count=len(cities),
        cities=cities,
    )


@router.get(
    "/languages",
    summary="Get Supported Languages",
    description="Returns list of supported languages for autocomplete",
)
def get_languages() -> dict:
    """Get list of supported languages."""
    return {
        "languages": settings.cities_languages,
        "default": "en",
    }
