from uuid import UUID
from fastapi import APIRouter, Depends, Query, status, HTTPException

from app.routes.dependencies import RouteServiceDep, CurrentUserOptional, CurrentUser
from app.routes.schemas import (
    TripListResponse, TripDetailResponse, CheckpointProgressResponse,
    UserActiveTripResponse, MarkVisitedRequest, UpdateAudioStatusRequest,
    TripListItem, UserTripProgress
)

router = APIRouter()


# ========== Phase 1: Read Endpoints ==========

@router.get("", response_model=TripListResponse)
def list_trips(
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    city_id: int | None = Query(None, description="Filter by city geonameid"),
    lat: float | None = Query(None, ge=-90, le=90, description="User latitude for nearby filter"),
    lon: float | None = Query(None, ge=-180, le=180, description="User longitude for nearby filter"),
    nearby_km: float = Query(50.0, ge=1, le=500, description="Radius in km for nearby search"),
    status: list[str] | None = Query(None, description="Filter by trip status"),
    search: str | None = Query(None, min_length=2, max_length=100, description="Search in title and description"),
    wished: bool | None = Query(None, description="Filter by wished status (requires auth)"),
    lang: str = Query("en", description="Language for i18n content"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List available trips with optional filters.

    - **city_id**: Filter trips by city
    - **lat/lon**: Filter trips near user location (uses first checkpoint)
    - **search**: Search in trip titles and descriptions
    - **status**: Filter by trip status (published, coming_soon, etc)
    - **wished**: Filter by user's wished status (true=only wished, false=exclude wished)
    - **lang**: Language for titles and descriptions
    """
    user_id = current_user.id if current_user else None
    return route_service.list_trips(
        user_id=user_id,
        city_id=city_id,
        lat=lat,
        lon=lon,
        nearby_km=nearby_km,
        status_filter=status,
        search=search,
        wished=wished,
        limit=limit,
        offset=offset,
        lang=lang
    )


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get detailed trip information including current published route.

    Returns 404 if trip not found or not published.
    """
    user_id = current_user.id if current_user else None
    result = route_service.get_trip_detail(trip_id, user_id=user_id, lang=lang)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return result


@router.get("/{trip_id}/checkpoints", response_model=list[CheckpointProgressResponse])
def get_trip_checkpoints(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get all checkpoints for a trip.

    If user has an active session, returns checkpoints from the locked route.
    Otherwise returns checkpoints from current published route.
    Includes user progress if authenticated.
    """
    user_id = current_user.id if current_user else None
    return route_service.get_trip_checkpoints(trip_id, user_id=user_id, lang=lang)


# ========== Phase 2: User Progress Endpoints ==========

@router.post(
    "/checkpoints/{checkpoint_id}/visited",
    response_model=CheckpointProgressResponse
)
def mark_checkpoint_visited(
    checkpoint_id: UUID,
    data: MarkVisitedRequest,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Mark a checkpoint as GPS visited.

    Called when user's device enters the checkpoint's trigger zone.
    Updates visited=True and visited_at timestamp.
    May trigger automatic route completion if all checkpoints done.
    """
    result = route_service.mark_checkpoint_visited(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkpoint not found"
        )
    return result


@router.post(
    "/checkpoints/{checkpoint_id}/audio-status",
    response_model=CheckpointProgressResponse
)
def update_audio_status(
    checkpoint_id: UUID,
    data: UpdateAudioStatusRequest,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Update audio listening status for a checkpoint.

    Status progression: none -> started -> completed
    Sets appropriate timestamps (audio_started_at, audio_completed_at).
    May trigger automatic route completion if all audio completed.
    """
    result = route_service.update_audio_status(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        status=data.status
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkpoint not found"
        )
    return result


@router.get("/me/trips", response_model=list[UserActiveTripResponse])
def get_my_trips(
    route_service: RouteServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get user's active trip sessions with progress.

    Returns all trips the user has started (both in-progress and completed).
    Each trip includes progress information (checkpoints visited, audio completed, etc).
    """
    return route_service.get_user_active_trips(
        user_id=current_user.id,
        lang=lang
    )


@router.post(
    "/{trip_id}/start",
    response_model=UserActiveTripResponse,
    status_code=status.HTTP_201_CREATED
)
def start_trip(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Start a trip session.

    Locks the user to the current published route of the trip.
    If already started, returns existing session (idempotent).
    """
    result = route_service.start_trip(
        user_id=current_user.id,
        trip_id=trip_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found or not published"
        )
    return result


@router.post("/{trip_id}/finish", response_model=UserActiveTripResponse)
def finish_trip(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Manually finish a trip.

    Marks the trip as completed with completion_type='manual'.
    Returns 404 if no active session exists for this trip.
    """
    result = route_service.finish_trip(
        user_id=current_user.id,
        trip_id=trip_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session for this trip"
        )
    return result
