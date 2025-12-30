from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============ Type Aliases ============

TripStatusType = Literal["draft", "published", "coming_soon", "archived"]
RouteStatusType = Literal["draft", "review", "published", "superseded"]
AudioListenStatusType = Literal["none", "started", "completed"]
CompletionTypeValue = Literal["manual", "automatic"]


# ============ Response Schemas ============

class CheckpointResponse(BaseModel):
    """Single checkpoint in a route"""
    id: UUID
    seq_no: int
    display_number: int | None
    is_visible: bool
    title: str  # Resolved from title_i18n
    description: str | None  # Resolved from description_i18n
    lat: float
    lon: float
    trigger_radius_m: int
    is_free_preview: bool

    model_config = {"from_attributes": True}


class CheckpointProgressResponse(CheckpointResponse):
    """Checkpoint with user progress data"""
    visited: bool = False
    visited_at: datetime | None = None
    audio_status: AudioListenStatusType = "none"
    audio_started_at: datetime | None = None
    audio_completed_at: datetime | None = None


class UserTripProgress(BaseModel):
    """User's progress on a trip"""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completion_type: CompletionTypeValue | None = None
    checkpoints_visited: int = 0
    checkpoints_total: int = 0
    audio_completed: int = 0
    progress_percent: float = 0.0


class TripListItem(BaseModel):
    """Trip summary for list views"""
    id: UUID
    slug: str
    status: TripStatusType
    title: str  # From current route
    summary: str | None
    duration_min: int | None
    distance_m: int | None
    ascent_m: int | None
    descent_m: int | None
    languages: list[str]
    free_checkpoint_limit: int
    price_amount: Decimal | None
    price_currency: str | None
    city_id: int
    city_name: str
    checkpoint_count: int
    user_progress: "UserTripProgress | None" = None
    is_wished: bool = False  # True if user has active wish for this trip

    model_config = {"from_attributes": True}


class TripDetailResponse(BaseModel):
    """Complete trip details"""
    id: UUID
    slug: str
    status: TripStatusType
    city_id: int
    city_name: str
    route_id: UUID
    version_no: int
    title: str
    summary: str | None
    languages: list[str]
    duration_min: int | None
    distance_m: int | None
    ascent_m: int | None
    descent_m: int | None
    geojson: dict | None
    free_checkpoint_limit: int
    price_amount: Decimal | None
    price_currency: str | None
    checkpoint_count: int
    created_at: datetime
    published_at: datetime | None
    user_progress: "UserTripProgress | None" = None

    model_config = {"from_attributes": True}


class UserActiveTripResponse(BaseModel):
    """User's active trip with locked route"""
    id: UUID
    trip: TripListItem
    locked_route_id: UUID
    started_at: datetime
    completed_at: datetime | None
    completion_type: CompletionTypeValue | None
    progress: UserTripProgress

    model_config = {"from_attributes": True}


class TripListResponse(BaseModel):
    """Paginated list of trips"""
    count: int
    trips: list[TripListItem]


# ============ Request Schemas ============

class MarkVisitedRequest(BaseModel):
    """Mark checkpoint as visited with user location"""
    lat: float = Field(..., ge=-90, le=90, description="User latitude")
    lon: float = Field(..., ge=-180, le=180, description="User longitude")


class UpdateAudioStatusRequest(BaseModel):
    """Update checkpoint audio listening status"""
    status: AudioListenStatusType


class StartTripRequest(BaseModel):
    """Start a new trip (empty for now, could add language preference later)"""
    pass


class FinishTripRequest(BaseModel):
    """Finish a trip (empty for now, could add feedback later)"""
    pass


# ============ Admin Request Schemas ============

class TripCreateRequest(BaseModel):
    """Create a new trip"""
    city_id: int = Field(..., description="City geonameid")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly trip identifier")
    status: TripStatusType = "draft"


class TripUpdateRequest(BaseModel):
    """Update trip metadata"""
    slug: str | None = None
    status: TripStatusType | None = None


class RouteCreateRequest(BaseModel):
    """Create a new route from GeoJSON"""
    title_i18n: dict[str, str] = Field(..., description="Titles in different languages")
    summary_i18n: dict[str, str] | None = None
    languages: list[str] = Field(..., min_length=1)
    duration_min: int | None = None
    distance_m: int | None = None
    ascent_m: int | None = None
    descent_m: int | None = None
    geojson: dict = Field(..., description="Full GeoJSON FeatureCollection")
    free_checkpoint_limit: int = Field(0, ge=0)
    price_amount: Decimal | None = None
    price_currency: str | None = Field(None, min_length=3, max_length=3)


class RouteUpdateRequest(BaseModel):
    """Update route metadata"""
    title_i18n: dict[str, str] | None = None
    summary_i18n: dict[str, str] | None = None
    duration_min: int | None = None
    distance_m: int | None = None
    ascent_m: int | None = None
    descent_m: int | None = None
    free_checkpoint_limit: int | None = Field(None, ge=0)
    price_amount: Decimal | None = None
    price_currency: str | None = None


class PublishRouteRequest(BaseModel):
    """Publish a route"""
    route_id: UUID


class CheckpointUpdateRequest(BaseModel):
    """Update checkpoint metadata"""
    display_number: int | None = None
    is_visible: bool | None = None
    title_i18n: dict[str, str] | None = None
    description_i18n: dict[str, str] | None = None
    trigger_radius_m: int | None = Field(None, gt=0)
    is_free_preview: bool | None = None


# ============ Admin Response Schemas ============

class TripAdminResponse(BaseModel):
    """Trip for admin views (includes all routes)"""
    id: UUID
    city_id: int
    city_name: str
    slug: str
    status: TripStatusType
    published_route_id: UUID | None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    route_count: int = 0

    model_config = {"from_attributes": True}


class RouteAdminResponse(BaseModel):
    """Route for admin views"""
    id: UUID
    trip_id: UUID
    version_no: int
    status: RouteStatusType
    title_i18n: dict[str, str]
    summary_i18n: dict[str, str] | None
    languages: list[str]
    duration_min: int | None
    distance_m: int | None
    ascent_m: int | None
    descent_m: int | None
    free_checkpoint_limit: int
    price_amount: Decimal | None
    price_currency: str | None
    published_at: datetime | None
    created_at: datetime
    created_by_user_id: int
    checkpoint_count: int = 0

    model_config = {"from_attributes": True}


class CheckpointLocation(BaseModel):
    """Checkpoint location coordinates"""
    lat: float
    lon: float


class CheckpointAdminResponse(BaseModel):
    """Checkpoint for admin views"""
    id: UUID
    route_id: UUID
    seq_no: int
    display_number: int | None
    is_visible: bool
    source_point_id: int | None
    title_i18n: dict[str, str]
    description_i18n: dict[str, str] | None
    location: CheckpointLocation
    trigger_radius_m: int
    is_free_preview: bool
    osm_way_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoutesListResponse(BaseModel):
    """List of routes for a trip"""
    trip_id: UUID
    routes: list[RouteAdminResponse]
