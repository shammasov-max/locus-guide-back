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
