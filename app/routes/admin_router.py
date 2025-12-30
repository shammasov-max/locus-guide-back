"""Admin endpoints for trip management."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.routes.dependencies import RouteServiceDep
from app.auth.dependencies import RequireEditor
from app.routes.schemas import (
    TripCreateRequest,
    TripUpdateRequest,
    TripAdminResponse,
    RouteCreateRequest,
    RouteUpdateRequest,
    RouteAdminResponse,
    PublishRouteRequest,
    RoutesListResponse,
    CheckpointUpdateRequest,
    CheckpointAdminResponse,
)

router = APIRouter()


# ========== Trip CRUD ==========


@router.post("", response_model=TripAdminResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    data: TripCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new trip (editor/admin only)."""
    result = route_service.create_trip(
        user_id=current_user.id,
        city_id=data.city_id,
        slug=data.slug,
        status=data.status,
    )
    return route_service.get_trip_admin(result.id)


@router.get("", response_model=dict)  # {count, trips}
def list_trips_admin(
    route_service: RouteServiceDep,
    current_user: RequireEditor,
    city_id: int | None = Query(None),
    status: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all trips for admin (includes drafts, archived). Requires editor role."""
    return route_service.list_trips_admin(
        city_id=city_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{trip_id}", response_model=TripAdminResponse)
def get_trip_admin(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Get trip details for admin. Requires editor role."""
    result = route_service.get_trip_admin(trip_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trip not found")
    return result


@router.patch("/{trip_id}", response_model=TripAdminResponse)
def update_trip(
    trip_id: UUID,
    data: TripUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update trip metadata. Requires editor role."""
    result = route_service.update_trip(
        trip_id=trip_id,
        slug=data.slug,
        status=data.status,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Trip not found")
    return route_service.get_trip_admin(trip_id)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Delete a trip. Requires editor role."""
    if not route_service.delete_trip(trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")


# ========== Routes ==========


@router.get("/{trip_id}/routes", response_model=RoutesListResponse)
def list_trip_routes(
    trip_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """List all routes of a trip. Requires editor role."""
    routes = route_service.get_trip_routes(trip_id)
    return {"trip_id": trip_id, "routes": routes}


@router.post(
    "/{trip_id}/routes",
    response_model=RouteAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route(
    trip_id: UUID,
    data: RouteCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new route from GeoJSON. Requires editor role."""
    result = route_service.create_route(
        trip_id=trip_id,
        user_id=current_user.id,
        data=data.model_dump(),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Trip not found")
    # Return the route with checkpoint count
    routes = route_service.get_trip_routes(trip_id)
    return next((r for r in routes if r["id"] == result.id), None)


@router.patch("/routes/{route_id}", response_model=RouteAdminResponse)
def update_route(
    route_id: UUID,
    data: RouteUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update route metadata. Requires editor role."""
    result = route_service.update_route(
        route_id, data.model_dump(exclude_unset=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    # Return full route response
    routes = route_service.get_trip_routes(result.trip_id)
    return next((r for r in routes if r["id"] == route_id), None)


@router.post("/{trip_id}/publish", response_model=TripAdminResponse)
def publish_route(
    trip_id: UUID,
    data: PublishRouteRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Publish a route. Requires editor role."""
    result = route_service.publish_route(trip_id, data.route_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trip or route not found")
    return route_service.get_trip_admin(trip_id)


# ========== Checkpoints ==========


@router.get(
    "/routes/{route_id}/checkpoints", response_model=list[CheckpointAdminResponse]
)
def get_route_checkpoints(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Get all checkpoints for a route. Requires editor role."""
    return route_service.get_route_checkpoints_admin(route_id)


@router.patch("/checkpoints/{checkpoint_id}", response_model=CheckpointAdminResponse)
def update_checkpoint(
    checkpoint_id: UUID,
    data: CheckpointUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update checkpoint metadata. Requires editor role."""
    result = route_service.update_checkpoint(
        checkpoint_id, data.model_dump(exclude_unset=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    # Return full response
    checkpoints = route_service.get_route_checkpoints_admin(result.route_id)
    return next((c for c in checkpoints if c["id"] == checkpoint_id), None)
