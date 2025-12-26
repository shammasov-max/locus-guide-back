from uuid import UUID
from fastapi import APIRouter, Depends, Query, status, HTTPException

from app.routes.dependencies import RouteServiceDep, CurrentUserOptional, CurrentUser
from app.routes.schemas import (
    RouteListResponse, RouteDetailResponse, CheckpointProgressResponse,
    UserActiveRouteResponse, MarkVisitedRequest, UpdateAudioStatusRequest,
    RouteListItem, UserRouteProgress
)

router = APIRouter()


# ========== Phase 1: Read Endpoints ==========

@router.get("", response_model=RouteListResponse)
def list_routes(
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    city_id: int | None = Query(None, description="Filter by city geonameid"),
    lat: float | None = Query(None, ge=-90, le=90, description="User latitude for nearby filter"),
    lon: float | None = Query(None, ge=-180, le=180, description="User longitude for nearby filter"),
    nearby_km: float = Query(50.0, ge=1, le=500, description="Radius in km for nearby search"),
    status: list[str] | None = Query(None, description="Filter by route status"),
    search: str | None = Query(None, min_length=2, max_length=100, description="Search in title and description"),
    wished: bool | None = Query(None, description="Filter by wished status (requires auth)"),
    lang: str = Query("en", description="Language for i18n content"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List available routes with optional filters.

    - **city_id**: Filter routes by city
    - **lat/lon**: Filter routes near user location (uses first checkpoint)
    - **search**: Search in route titles and descriptions
    - **status**: Filter by route status (published, coming_soon, etc)
    - **wished**: Filter by user's wished status (true=only wished, false=exclude wished)
    - **lang**: Language for titles and descriptions
    """
    user_id = current_user.id if current_user else None
    return route_service.list_routes(
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


@router.get("/{route_id}", response_model=RouteDetailResponse)
def get_route(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get detailed route information including current published version.

    Returns 404 if route not found or not published.
    """
    user_id = current_user.id if current_user else None
    result = route_service.get_route_detail(route_id, user_id=user_id, lang=lang)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return result


@router.get("/{route_id}/checkpoints", response_model=list[CheckpointProgressResponse])
def get_route_checkpoints(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUserOptional,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get all checkpoints for a route.

    If user has an active session, returns checkpoints from the locked version.
    Otherwise returns checkpoints from current published version.
    Includes user progress if authenticated.
    """
    user_id = current_user.id if current_user else None
    return route_service.get_route_checkpoints(route_id, user_id=user_id, lang=lang)


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


@router.get("/me/routes", response_model=list[UserActiveRouteResponse])
def get_my_routes(
    route_service: RouteServiceDep,
    current_user: CurrentUser,
    lang: str = Query("en", description="Language for i18n content"),
):
    """
    Get user's active route sessions with progress.

    Returns all routes the user has started (both in-progress and completed).
    Each route includes progress information (checkpoints visited, audio completed, etc).
    """
    return route_service.get_user_active_routes(
        user_id=current_user.id,
        lang=lang
    )


@router.post(
    "/{route_id}/start",
    response_model=UserActiveRouteResponse,
    status_code=status.HTTP_201_CREATED
)
def start_route(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Start a route session.

    Locks the user to the current published version of the route.
    If already started, returns existing session (idempotent).
    """
    result = route_service.start_route(
        user_id=current_user.id,
        route_id=route_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found or not published"
        )
    return result


@router.post("/{route_id}/finish", response_model=UserActiveRouteResponse)
def finish_route(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: CurrentUser,
):
    """
    Manually finish a route.

    Marks the route as completed with completion_type='manual'.
    Returns 404 if no active session exists for this route.
    """
    result = route_service.finish_route(
        user_id=current_user.id,
        route_id=route_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session for this route"
        )
    return result
