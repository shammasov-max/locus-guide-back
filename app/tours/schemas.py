from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Tour schemas
class TourBase(BaseModel):
    title_i18n: dict[str, str]
    description_i18n: dict[str, str] | None = None
    price_usd: float | None = Field(None, ge=0, le=99.99)
    city_id: int | None = None
    is_coming_soon: bool = False


class TourCreate(TourBase):
    pass


class TourUpdate(BaseModel):
    title_i18n: dict[str, str] | None = None
    description_i18n: dict[str, str] | None = None
    price_usd: float | None = Field(None, ge=0, le=99.99)
    city_id: int | None = None
    is_coming_soon: bool | None = None


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    status: str
    geojson: dict | None = None
    waypoint_guids: list[UUID] | None = None
    distance_m: int | None = None
    elevation_m: int | None = None
    estimated_min: int | None = None
    languages: dict | None = None
    created_at: datetime


class TourResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city_id: int | None
    title_i18n: dict[str, str]
    description_i18n: dict[str, str] | None
    price_usd: float | None
    is_coming_soon: bool
    is_archived: bool
    active_route: RouteResponse | None = None
    created_at: datetime
    updated_at: datetime | None


class TourListResponse(BaseModel):
    count: int
    tours: list[TourResponse]


class TourPreviewResponse(BaseModel):
    tour_id: int
    waypoints: list["WaypointResponse"]


# Waypoint schemas
class WaypointCreate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    description_i18n: dict[str, str] | None = None
    is_checkpoint: bool = True


class WaypointUpdate(BaseModel):
    description_i18n: dict[str, str] | None = None


class WaypointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guid: UUID
    lat: float
    lon: float
    description_i18n: dict[str, str] | None
    is_checkpoint: bool
    created_at: datetime


# Route schemas
class RouteUpdate(BaseModel):
    geojson: dict | None = None
    waypoint_guids: list[UUID] | None = None
    distance_m: int | None = None
    elevation_m: int | None = None
    estimated_min: int | None = None
    languages: dict | None = None


class RouteHistoryResponse(BaseModel):
    count: int
    routes: list[RouteResponse]


# Run schemas
class RunCreate(BaseModel):
    tour_id: int
    is_simulation: bool = False


class RunUpdate(BaseModel):
    completed_checkpoints: list[UUID] | None = None
    last_position_lat: float | None = Field(None, ge=-90, le=90)
    last_position_lon: float | None = Field(None, ge=-180, le=180)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guid: UUID
    route_id: int
    tour_id: int
    started_at: datetime
    completed_at: datetime | None
    abandoned_at: datetime | None
    completed_checkpoints: list[UUID] | None
    is_simulation: bool
    last_position_lat: float | None = None
    last_position_lon: float | None = None
    updated_at: datetime | None


class RunListResponse(BaseModel):
    count: int
    runs: list[RunResponse]


# User Lists schemas
class AwaitListItemResponse(BaseModel):
    tour_id: int
    created_at: datetime


class AwaitListResponse(BaseModel):
    count: int
    items: list[AwaitListItemResponse]


class WatchListItemResponse(BaseModel):
    city_id: int
    created_at: datetime


class WatchListResponse(BaseModel):
    count: int
    items: list[WatchListItemResponse]


class EntitlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tour_id: int
    bundle_id: int | None
    source: str
    created_at: datetime


class EntitlementsResponse(BaseModel):
    count: int
    entitlements: list[EntitlementResponse]


# Bundle schemas
class BundleCreate(BaseModel):
    title_i18n: dict[str, str]
    description_i18n: dict[str, str] | None = None
    price_usd: float = Field(..., ge=0, le=999.99)
    tour_ids: list[int] = Field(..., min_length=2)


class BundleTourResponse(BaseModel):
    tour_id: int
    display_order: int
    title_i18n: dict[str, str]
    price_usd: float | None


class BundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title_i18n: dict[str, str]
    description_i18n: dict[str, str] | None
    price_usd: float
    discount_percent: float | None = None
    is_deleted: bool
    tours: list[BundleTourResponse] = []
    created_at: datetime


class BundleListResponse(BaseModel):
    count: int
    bundles: list[BundleResponse]


# Editor schemas
class EditorResponse(BaseModel):
    account_id: int
    email: str
    display_name: str | None
    created_at: datetime


class EditorListResponse(BaseModel):
    count: int
    editors: list[EditorResponse]


# Common
class MessageResponse(BaseModel):
    message: str
