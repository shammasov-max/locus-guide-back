"""Pydantic schemas for wishes module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ============ Response Schemas ============

class WishedRouteResponse(BaseModel):
    """User's wished tour with details."""
    tour_id: UUID
    tour_slug: str
    tour_title: str
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
    has_routes: bool  # True if city now has published tours
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWishesResponse(BaseModel):
    """All user's active wishes and wants."""
    wished_tours: list[WishedRouteResponse]
    wanted_cities: list[WantedCityResponse]


class WishActionResponse(BaseModel):
    """Response for wish/unwish actions."""
    success: bool
    is_active: bool
    message: str


# ============ Admin Analytics Schemas ============

class RouteWishStatsResponse(BaseModel):
    """Aggregated wish stats for a tour."""
    tour_id: UUID
    tour_slug: str
    tour_title: str
    city_id: int
    city_name: str
    tour_status: str
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
    tour_count: int
    active_want_count: int
    total_want_count: int  # Including inactive (historical)

    model_config = {"from_attributes": True}


class WishStatsListResponse(BaseModel):
    """Paginated list of tour wish stats."""
    count: int
    tours: list[RouteWishStatsResponse]


class WantStatsListResponse(BaseModel):
    """Paginated list of city want stats."""
    count: int
    cities: list[CityWantStatsResponse]
