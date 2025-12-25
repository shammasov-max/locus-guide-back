"""Admin endpoints for route management."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.routes.dependencies import RouteServiceDep
from app.auth.dependencies import RequireEditor
from app.routes.schemas import (
    RouteCreateRequest,
    RouteUpdateRequest,
    RouteAdminResponse,
    RouteVersionCreateRequest,
    RouteVersionUpdateRequest,
    RouteVersionAdminResponse,
    PublishVersionRequest,
    RouteVersionsListResponse,
    CheckpointUpdateRequest,
    CheckpointAdminResponse,
)

router = APIRouter()


# ========== Route CRUD ==========


@router.post("", response_model=RouteAdminResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    data: RouteCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new route (editor/admin only)."""
    result = route_service.create_route(
        user_id=current_user.id,
        city_id=data.city_id,
        slug=data.slug,
        status=data.status,
    )
    return route_service.get_route_admin(result.id)


@router.get("", response_model=dict)  # {count, routes}
def list_routes_admin(
    route_service: RouteServiceDep,
    current_user: RequireEditor,
    city_id: int | None = Query(None),
    status: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all routes for admin (includes drafts, archived). Requires editor role."""
    return route_service.list_routes_admin(
        city_id=city_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{route_id}", response_model=RouteAdminResponse)
def get_route_admin(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Get route details for admin. Requires editor role."""
    result = route_service.get_route_admin(route_id)
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    return result


@router.patch("/{route_id}", response_model=RouteAdminResponse)
def update_route(
    route_id: UUID,
    data: RouteUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update route metadata. Requires editor role."""
    result = route_service.update_route(
        route_id=route_id,
        slug=data.slug,
        status=data.status,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    return route_service.get_route_admin(route_id)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Delete a route. Requires editor role."""
    if not route_service.delete_route(route_id):
        raise HTTPException(status_code=404, detail="Route not found")


# ========== Route Versions ==========


@router.get("/{route_id}/versions", response_model=RouteVersionsListResponse)
def list_route_versions(
    route_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """List all versions of a route. Requires editor role."""
    versions = route_service.get_route_versions(route_id)
    return {"route_id": route_id, "versions": versions}


@router.post(
    "/{route_id}/versions",
    response_model=RouteVersionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route_version(
    route_id: UUID,
    data: RouteVersionCreateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Create a new route version from GeoJSON. Requires editor role."""
    result = route_service.create_route_version(
        route_id=route_id,
        user_id=current_user.id,
        data=data.model_dump(),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    # Return the version with checkpoint count
    versions = route_service.get_route_versions(route_id)
    return next((v for v in versions if v["id"] == result.id), None)


@router.patch("/versions/{version_id}", response_model=RouteVersionAdminResponse)
def update_route_version(
    version_id: UUID,
    data: RouteVersionUpdateRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Update route version metadata. Requires editor role."""
    result = route_service.update_route_version(
        version_id, data.model_dump(exclude_unset=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    # Return full version response
    versions = route_service.get_route_versions(result.route_id)
    return next((v for v in versions if v["id"] == version_id), None)


@router.post("/{route_id}/publish", response_model=RouteAdminResponse)
def publish_version(
    route_id: UUID,
    data: PublishVersionRequest,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Publish a route version. Requires editor role."""
    result = route_service.publish_version(route_id, data.version_id)
    if not result:
        raise HTTPException(status_code=404, detail="Route or version not found")
    return route_service.get_route_admin(route_id)


# ========== Checkpoints ==========


@router.get(
    "/versions/{version_id}/checkpoints", response_model=list[CheckpointAdminResponse]
)
def get_version_checkpoints(
    version_id: UUID,
    route_service: RouteServiceDep,
    current_user: RequireEditor,
):
    """Get all checkpoints for a version. Requires editor role."""
    return route_service.get_version_checkpoints_admin(version_id)


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
    checkpoints = route_service.get_version_checkpoints_admin(result.route_version_id)
    return next((c for c in checkpoints if c["id"] == checkpoint_id), None)
