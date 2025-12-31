"""Admin endpoints for tour management."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.routes.dependencies import RouteServiceDep
from app.auth.dependencies import RequireEditor
from app.routes.schemas import (
    TourCreateRequest,
    TourUpdateRequest,
    TourAdminResponse,
    RouteCreateRequest,
    RouteUpdateRequest,
    RouteAdminResponse,
    PublishRouteRequest,
    RoutesListResponse,
    CheckpointUpdateRequest,
    CheckpointAdminResponse,
)

router = APIRouter()


# ========== Tour CRUD ==========


@router.post("", response_model=TourAdminResponse, status_code=status.HTTP_201_CREATED)
def create_tour(
    data: TourCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new tour (editor/admin only)."""
    result = route_service.create_tour(
        user_id=current_user.id,
        city_id=data.city_id,
        slug=data.slug,
        status=data.status,
    )
    return route_service.get_tour_admin(result.id)


@router.get("", response_model=dict)  # {count, tours}
def list_tours_admin(
    route_service: RouteServiceDep,
    current_user: RequireEditor,
    city_id: int | None = Query(None),
    status: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all tours for admin (includes drafts, archived). Requires editor role."""
    return route_service.list_tours_admin(
        city_id=city_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{tour_id}", response_model=TourAdminResponse)
def get_tour_admin(
    tour_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Get tour details for admin. Requires editor role."""
    result = route_service.get_tour_admin(tour_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tour not found")
    return result


@router.patch("/{tour_id}", response_model=TourAdminResponse)
def update_tour(
    tour_id: UUID,
    data: TourUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update tour metadata. Requires editor role."""
    result = route_service.update_tour(
        tour_id=tour_id,
        slug=data.slug,
        status=data.status,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Tour not found")
    return route_service.get_tour_admin(tour_id)


@router.delete("/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tour(
    tour_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Delete a tour. Requires editor role."""
    if not route_service.delete_tour(tour_id):
        raise HTTPException(status_code=404, detail="Tour not found")


# ========== Routes ==========


@router.get("/{tour_id}/routes", response_model=RoutesListResponse)
def list_tour_routes(
    tour_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """List all routes of a tour. Requires editor role."""
    routes = route_service.get_tour_routes(tour_id)
    return {"tour_id": tour_id, "routes": routes}


@router.post(
    "/{tour_id}/routes",
    response_model=RouteAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route(
    tour_id: UUID,
    data: RouteCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new route from GeoJSON. Requires editor role."""
    result = route_service.create_route(
        tour_id=tour_id,
        user_id=current_user.id,
        data=data.model_dump(),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Tour not found")
    # Return the route with checkpoint count
    routes = route_service.get_tour_routes(tour_id)
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
    routes = route_service.get_tour_routes(result.tour_id)
    return next((r for r in routes if r["id"] == route_id), None)


@router.post("/{tour_id}/publish", response_model=TourAdminResponse)
def publish_route(
    tour_id: UUID,
    data: PublishRouteRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Publish a route. Requires editor role."""
    result = route_service.publish_route(tour_id, data.route_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tour or route not found")
    return route_service.get_tour_admin(tour_id)


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
