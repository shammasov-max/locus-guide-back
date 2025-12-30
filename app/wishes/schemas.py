"""Pydantic schemas for wishes module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ============ Response Schemas ============

class WishedRouteResponse(BaseModel):
    """User's wished trip with details."""
    trip_id: UUID
    trip_slug: str
    trip_title: str
    city_id: int
    city_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WantedCityResponse(BaseModel):
    """User's wanted city with details."""
    geonameid: int
    city_name: str
    country_code: str
    is_active: bool
    has_routes: bool  # True if city now has published trips
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWishesResponse(BaseModel):
    """All user's active wishes and wants."""
    wished_trips: list[WishedRouteResponse]
    wanted_cities: list[WantedCityResponse]


class WishActionResponse(BaseModel):
    """Response for wish/unwish actions."""
    success: bool
    is_active: bool
    message: str


# ============ Admin Analytics Schemas ============

class RouteWishStatsResponse(BaseModel):
    """Aggregated wish stats for a trip."""
    trip_id: UUID
    trip_slug: str
    trip_title: str
    city_id: int
    city_name: str
    trip_status: str
    active_wish_count: int
    total_wish_count: int  # Including inactive (historical)

    model_config = {"from_attributes": True}


class CityWantStatsResponse(BaseModel):
    """Aggregated want stats for a city."""
    geonameid: int
    city_name: str
    country_code: str
    country_name: str
    population: int
    has_routes: bool
    trip_count: int
    active_want_count: int
    total_want_count: int  # Including inactive (historical)

    model_config = {"from_attributes": True}


class WishStatsListResponse(BaseModel):
    """Paginated list of trip wish stats."""
    count: int
    trips: list[RouteWishStatsResponse]


class WantStatsListResponse(BaseModel):
    """Paginated list of city want stats."""
    count: int
    cities: list[CityWantStatsResponse]
