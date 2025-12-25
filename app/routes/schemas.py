from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============ Type Aliases ============

RouteStatusType = Literal["draft", "published", "coming_soon", "archived"]
RouteVersionStatusType = Literal["draft", "review", "published", "superseded"]
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


class UserRouteProgress(BaseModel):
    """User's progress on a route"""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completion_type: CompletionTypeValue | None = None
    checkpoints_visited: int = 0
    checkpoints_total: int = 0
    audio_completed: int = 0
    progress_percent: float = 0.0


class RouteListItem(BaseModel):
    """Route summary for list views"""
    id: UUID
    slug: str
    status: RouteStatusType
    title: str  # From current version
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
    user_progress: "UserRouteProgress | None" = None

    model_config = {"from_attributes": True}


class RouteDetailResponse(BaseModel):
    """Complete route details"""
    id: UUID
    slug: str
    status: RouteStatusType
    city_id: int
    city_name: str
    version_id: UUID
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
    user_progress: "UserRouteProgress | None" = None

    model_config = {"from_attributes": True}


class UserActiveRouteResponse(BaseModel):
    """User's active route with locked version"""
    id: UUID
    route: RouteListItem
    locked_version_id: UUID
    started_at: datetime
    completed_at: datetime | None
    completion_type: CompletionTypeValue | None
    progress: UserRouteProgress

    model_config = {"from_attributes": True}


class RouteListResponse(BaseModel):
    """Paginated list of routes"""
    count: int
    routes: list[RouteListItem]


# ============ Request Schemas ============

class MarkVisitedRequest(BaseModel):
    """Mark checkpoint as visited with user location"""
    lat: float = Field(..., ge=-90, le=90, description="User latitude")
    lon: float = Field(..., ge=-180, le=180, description="User longitude")


class UpdateAudioStatusRequest(BaseModel):
    """Update checkpoint audio listening status"""
    status: AudioListenStatusType


class StartRouteRequest(BaseModel):
    """Start a new route (empty for now, could add language preference later)"""
    pass


class FinishRouteRequest(BaseModel):
    """Finish a route (empty for now, could add feedback later)"""
    pass


# ============ Admin Request Schemas ============

class RouteCreateRequest(BaseModel):
    """Create a new route"""
    city_id: int = Field(..., description="City geonameid")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly route identifier")
    status: RouteStatusType = "draft"


class RouteUpdateRequest(BaseModel):
    """Update route metadata"""
    slug: str | None = None
    status: RouteStatusType | None = None


class RouteVersionCreateRequest(BaseModel):
    """Create a new route version from GeoJSON"""
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


class RouteVersionUpdateRequest(BaseModel):
    """Update route version metadata"""
    title_i18n: dict[str, str] | None = None
    summary_i18n: dict[str, str] | None = None
    duration_min: int | None = None
    distance_m: int | None = None
    ascent_m: int | None = None
    descent_m: int | None = None
    free_checkpoint_limit: int | None = Field(None, ge=0)
    price_amount: Decimal | None = None
    price_currency: str | None = None


class PublishVersionRequest(BaseModel):
    """Publish a route version"""
    version_id: UUID


class CheckpointUpdateRequest(BaseModel):
    """Update checkpoint metadata"""
    display_number: int | None = None
    is_visible: bool | None = None
    title_i18n: dict[str, str] | None = None
    description_i18n: dict[str, str] | None = None
    trigger_radius_m: int | None = Field(None, gt=0)
    is_free_preview: bool | None = None


# ============ Admin Response Schemas ============

class RouteAdminResponse(BaseModel):
    """Route for admin views (includes all versions)"""
    id: UUID
    city_id: int
    city_name: str
    slug: str
    status: RouteStatusType
    published_version_id: UUID | None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    version_count: int = 0

    model_config = {"from_attributes": True}


class RouteVersionAdminResponse(BaseModel):
    """Route version for admin views"""
    id: UUID
    route_id: UUID
    version_no: int
    status: RouteVersionStatusType
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
    route_version_id: UUID
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


class RouteVersionsListResponse(BaseModel):
    """List of versions for a route"""
    route_id: UUID
    versions: list[RouteVersionAdminResponse]
