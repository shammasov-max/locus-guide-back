from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminAccount, CurrentAccount, EditorAccount
from app.common.database import get_db
from app.common.exceptions import NotFoundException
from app.tours import service
from app.tours.schemas import (
    AwaitListResponse,
    BundleCreate,
    BundleListResponse,
    BundleResponse,
    EditorListResponse,
    EditorResponse,
    EntitlementsResponse,
    RouteHistoryResponse,
    RouteResponse,
    RouteUpdate,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunUpdate,
    TourCreate,
    TourListResponse,
    TourPreviewResponse,
    TourResponse,
    TourUpdate,
    WatchListResponse,
    WaypointCreate,
    WaypointResponse,
    WaypointUpdate,
)

# ============ Public Tours Router ============
router = APIRouter(prefix="/api/v1/tours", tags=["tours"])


@router.get("", response_model=TourListResponse)
async def list_tours(
    db: Annotated[AsyncSession, Depends(get_db)],
    city_id: Annotated[int | None, Query()] = None,
    is_coming_soon: Annotated[bool | None, Query()] = None,
    lang: Annotated[str, Query()] = "en",
) -> TourListResponse:
    tours = await service.get_tours(db, city_id, is_coming_soon, lang)
    return TourListResponse(count=len(tours), tours=tours)


@router.get("/{tour_id}", response_model=TourResponse)
async def get_tour(
    tour_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourResponse:
    tour = await service.get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    return service._build_tour_response(tour)


@router.get("/{tour_id}/preview", response_model=TourPreviewResponse)
async def get_tour_preview(
    tour_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourPreviewResponse:
    waypoints = await service.get_tour_preview(db, tour_id)
    return TourPreviewResponse(tour_id=tour_id, waypoints=waypoints)


# ============ Bundles Router ============
bundles_router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])


@bundles_router.get("", response_model=BundleListResponse)
async def list_bundles(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BundleListResponse:
    bundles = await service.get_bundles(db)
    return BundleListResponse(count=len(bundles), bundles=bundles)


@bundles_router.get("/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BundleResponse:
    bundle = await service.get_bundle_by_id(db, bundle_id)
    if not bundle:
        raise NotFoundException("Bundle not found")
    return bundle


# ============ Runs Router ============
runs_router = APIRouter(prefix="/api/v1/me/runs", tags=["runs"])


@runs_router.get("", response_model=RunListResponse)
async def list_runs(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[bool, Query()] = False,
) -> RunListResponse:
    runs = await service.get_runs(db, account, active_only)
    return RunListResponse(count=len(runs), runs=runs)


@runs_router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    data: RunCreate,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    return await service.create_run(db, account, data)


@runs_router.get("/{guid}", response_model=RunResponse)
async def get_run(
    guid: UUID,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    return await service.get_run(db, account, guid)


@runs_router.patch("/{guid}", response_model=RunResponse)
async def update_run(
    guid: UUID,
    data: RunUpdate,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    return await service.update_run(db, account, guid, data)


@runs_router.post("/{guid}/abandon", response_model=RunResponse)
async def abandon_run(
    guid: UUID,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    return await service.abandon_run(db, account, guid)


@runs_router.post("/{guid}/complete", response_model=RunResponse)
async def complete_run(
    guid: UUID,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    return await service.complete_run(db, account, guid)


# ============ User Lists Router ============
user_lists_router = APIRouter(prefix="/api/v1/me", tags=["user-lists"])


@user_lists_router.get("/await-list", response_model=AwaitListResponse)
async def get_await_list(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AwaitListResponse:
    return await service.get_await_list(db, account)


@user_lists_router.put("/await-list/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_await_list(
    tour_id: int,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.add_to_await_list(db, account, tour_id)


@user_lists_router.delete("/await-list/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_await_list(
    tour_id: int,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.remove_from_await_list(db, account, tour_id)


@user_lists_router.get("/watch-list", response_model=WatchListResponse)
async def get_watch_list(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WatchListResponse:
    return await service.get_watch_list(db, account)


@user_lists_router.put("/watch-list/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_watch_list(
    city_id: int,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.add_to_watch_list(db, account, city_id)


@user_lists_router.delete("/watch-list/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watch_list(
    city_id: int,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.remove_from_watch_list(db, account, city_id)


@user_lists_router.get("/entitlements", response_model=EntitlementsResponse)
async def get_entitlements(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EntitlementsResponse:
    return await service.get_entitlements(db, account)


# ============ Editor Router ============
editor_router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


@editor_router.get("/tours", response_model=TourListResponse)
async def list_editor_tours(
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourListResponse:
    tours = await service.get_editor_tours(db, account)
    return TourListResponse(count=len(tours), tours=tours)


@editor_router.post("/tours", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def create_tour(
    data: TourCreate,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourResponse:
    return await service.create_tour(db, account, data)


@editor_router.get("/tours/{tour_id}", response_model=TourResponse)
async def get_editor_tour(
    tour_id: int,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourResponse:
    tour = await service.get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    return service._build_tour_response(tour)


@editor_router.patch("/tours/{tour_id}", response_model=TourResponse)
async def update_tour(
    tour_id: int,
    data: TourUpdate,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TourResponse:
    return await service.update_tour(db, account, tour_id, data)


@editor_router.delete("/tours/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_tour(
    tour_id: int,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.archive_tour(db, account, tour_id)


@editor_router.get("/tours/{tour_id}/draft", response_model=RouteResponse)
async def get_draft_route(
    tour_id: int,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RouteResponse:
    return await service.get_draft_route(db, account, tour_id)


@editor_router.patch("/tours/{tour_id}/draft", response_model=RouteResponse)
async def update_draft_route(
    tour_id: int,
    data: RouteUpdate,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RouteResponse:
    return await service.update_draft_route(db, account, tour_id, data)


@editor_router.post("/tours/{tour_id}/publish", response_model=RouteResponse)
async def publish_tour(
    tour_id: int,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RouteResponse:
    return await service.publish_tour(db, account, tour_id)


@editor_router.get("/tours/{tour_id}/history", response_model=RouteHistoryResponse)
async def get_route_history(
    tour_id: int,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RouteHistoryResponse:
    routes = await service.get_route_history(db, account, tour_id)
    return RouteHistoryResponse(count=len(routes), routes=routes)


@editor_router.post("/waypoints", response_model=WaypointResponse, status_code=status.HTTP_201_CREATED)
async def create_waypoint(
    data: WaypointCreate,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WaypointResponse:
    return await service.create_waypoint(db, account, data)


@editor_router.get("/waypoints/{guid}", response_model=WaypointResponse)
async def get_waypoint(
    guid: UUID,
    _: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WaypointResponse:
    waypoint = await service.get_waypoint(db, guid)
    if not waypoint:
        raise NotFoundException("Waypoint not found")
    return waypoint


@editor_router.patch("/waypoints/{guid}", response_model=WaypointResponse)
async def update_waypoint(
    guid: UUID,
    data: WaypointUpdate,
    account: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WaypointResponse:
    return await service.update_waypoint(db, account, guid, data)


@editor_router.delete("/waypoints/{guid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_waypoint(
    guid: UUID,
    _: EditorAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.delete_waypoint(db, guid)


# ============ Admin Router ============
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@admin_router.get("/editors", response_model=EditorListResponse)
async def list_editors(
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EditorListResponse:
    editors = await service.list_editors(db)
    return EditorListResponse(
        count=len(editors),
        editors=[
            EditorResponse(
                account_id=e.id,
                email=e.email,
                display_name=e.display_name,
                created_at=e.created_at,
            )
            for e in editors
        ],
    )


@admin_router.put("/editors/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_editor_role(
    account_id: int,
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.grant_editor_role(db, account_id)


@admin_router.delete("/editors/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_editor_role(
    account_id: int,
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.revoke_editor_role(db, account_id)


@admin_router.get("/bundles", response_model=BundleListResponse)
async def list_all_bundles(
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BundleListResponse:
    bundles = await service.get_all_bundles_admin(db)
    return BundleListResponse(count=len(bundles), bundles=bundles)


@admin_router.post("/bundles", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    data: BundleCreate,
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BundleResponse:
    return await service.create_bundle(db, data)


@admin_router.get("/bundles/{bundle_id}", response_model=BundleResponse)
async def get_admin_bundle(
    bundle_id: int,
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BundleResponse:
    bundle = await service.get_bundle_by_id(db, bundle_id)
    if not bundle:
        raise NotFoundException("Bundle not found")
    return bundle


@admin_router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: int,
    _: AdminAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.delete_bundle(db, bundle_id)
