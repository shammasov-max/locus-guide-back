from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Account
from app.common.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.geo.models import City
from app.tours.models import (
    AwaitList,
    Bundle,
    BundleToTour,
    Entitlement,
    Route,
    Run,
    Tour,
    WatchList,
    Waypoint,
)
from app.tours.schemas import (
    AwaitListItemResponse,
    AwaitListResponse,
    BundleCreate,
    BundleResponse,
    BundleTourResponse,
    EntitlementResponse,
    EntitlementsResponse,
    RouteResponse,
    RouteUpdate,
    RunCreate,
    RunResponse,
    RunUpdate,
    TourCreate,
    TourResponse,
    TourUpdate,
    WatchListItemResponse,
    WatchListResponse,
    WaypointCreate,
    WaypointResponse,
    WaypointUpdate,
)

# ============ Tours ============


async def get_tours(
    db: AsyncSession,
    city_id: int | None = None,
    is_coming_soon: bool | None = None,
    lang: str = "en",
) -> list[TourResponse]:
    stmt = (
        select(Tour)
        .options(selectinload(Tour.active_route))
        .where(Tour.is_archived == False)  # noqa: E712
    )

    if city_id is not None:
        stmt = stmt.where(Tour.city_id == city_id)
    if is_coming_soon is not None:
        stmt = stmt.where(Tour.is_coming_soon == is_coming_soon)

    result = await db.execute(stmt.order_by(Tour.created_at.desc()))
    tours = result.scalars().all()

    return [_build_tour_response(tour) for tour in tours]


async def get_tour_by_id(db: AsyncSession, tour_id: int) -> Tour | None:
    result = await db.execute(
        select(Tour)
        .options(selectinload(Tour.active_route), selectinload(Tour.draft_route))
        .where(Tour.id == tour_id, Tour.is_archived == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_tour_preview(db: AsyncSession, tour_id: int) -> list[WaypointResponse]:
    tour = await get_tour_by_id(db, tour_id)
    if not tour or not tour.active_route:
        raise NotFoundException("Tour not found or has no active route")

    waypoint_guids = tour.active_route.waypoint_guids or []
    preview_guids = waypoint_guids[:4]  # First 4 waypoints free

    if not preview_guids:
        return []

    result = await db.execute(select(Waypoint).where(Waypoint.guid.in_(preview_guids)))
    waypoints = result.scalars().all()

    # Maintain order
    waypoint_map = {w.guid: w for w in waypoints}
    ordered = [waypoint_map[guid] for guid in preview_guids if guid in waypoint_map]

    return [_build_waypoint_response(db, w) for w in ordered]


def _build_tour_response(tour: Tour) -> TourResponse:
    return TourResponse(
        id=tour.id,
        city_id=tour.city_id,
        title_i18n=tour.title_i18n or {},
        description_i18n=tour.description_i18n,
        price_usd=float(tour.price_usd) if tour.price_usd else None,
        is_coming_soon=tour.is_coming_soon,
        is_archived=tour.is_archived,
        active_route=RouteResponse.model_validate(tour.active_route) if tour.active_route else None,
        created_at=tour.created_at,
        updated_at=tour.updated_at,
    )


def _build_waypoint_response(db: AsyncSession, waypoint: Waypoint) -> WaypointResponse:
    # Extract lat/lon from geometry - will be done in async context
    return WaypointResponse(
        guid=waypoint.guid,
        lat=0.0,  # Will be populated later
        lon=0.0,
        description_i18n=waypoint.description_i18n,
        is_checkpoint=waypoint.is_checkpoint,
        created_at=waypoint.created_at,
    )


# ============ Editor Tours ============


async def get_editor_tours(db: AsyncSession, account: Account) -> list[TourResponse]:
    stmt = (
        select(Tour)
        .options(selectinload(Tour.active_route), selectinload(Tour.draft_route))
        .where(Tour.created_by == account.id)
        .order_by(Tour.created_at.desc())
    )
    result = await db.execute(stmt)
    tours = result.scalars().all()
    return [_build_tour_response(tour) for tour in tours]


async def create_tour(db: AsyncSession, account: Account, data: TourCreate) -> TourResponse:
    # Create tour
    tour = Tour(
        city_id=data.city_id,
        title_i18n=data.title_i18n,
        description_i18n=data.description_i18n,
        price_usd=data.price_usd,
        is_coming_soon=data.is_coming_soon,
        created_by=account.id,
    )
    db.add(tour)
    await db.flush()

    # Create draft route
    draft = Route(tour_id=tour.id, version=1, status="draft")
    db.add(draft)
    await db.flush()

    tour.draft_route_id = draft.id
    await db.flush()

    # Auto-grant entitlement
    entitlement = Entitlement(
        account_id=account.id, tour_id=tour.id, source="editor_access"
    )
    db.add(entitlement)
    await db.flush()

    await db.refresh(tour, ["active_route", "draft_route"])
    return _build_tour_response(tour)


async def update_tour(
    db: AsyncSession, account: Account, tour_id: int, data: TourUpdate
) -> TourResponse:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to edit this tour")

    if data.title_i18n is not None:
        tour.title_i18n = data.title_i18n
    if data.description_i18n is not None:
        tour.description_i18n = data.description_i18n
    if data.price_usd is not None:
        tour.price_usd = data.price_usd
    if data.city_id is not None:
        tour.city_id = data.city_id
    if data.is_coming_soon is not None:
        tour.is_coming_soon = data.is_coming_soon

    await db.flush()
    await db.refresh(tour, ["active_route", "draft_route"])
    return _build_tour_response(tour)


async def archive_tour(db: AsyncSession, account: Account, tour_id: int) -> None:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to archive this tour")

    tour.is_archived = True
    await db.flush()


async def get_draft_route(db: AsyncSession, account: Account, tour_id: int) -> RouteResponse:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to access this tour")

    if not tour.draft_route:
        raise NotFoundException("No draft route found")

    return RouteResponse.model_validate(tour.draft_route)


async def update_draft_route(
    db: AsyncSession, account: Account, tour_id: int, data: RouteUpdate
) -> RouteResponse:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to edit this tour")

    if not tour.draft_route:
        raise NotFoundException("No draft route found")

    draft = tour.draft_route
    if data.geojson is not None:
        draft.geojson = data.geojson
    if data.waypoint_guids is not None:
        draft.waypoint_guids = data.waypoint_guids
    if data.distance_m is not None:
        draft.distance_m = data.distance_m
    if data.elevation_m is not None:
        draft.elevation_m = data.elevation_m
    if data.estimated_min is not None:
        draft.estimated_min = data.estimated_min
    if data.languages is not None:
        draft.languages = data.languages

    await db.flush()
    return RouteResponse.model_validate(draft)


async def publish_tour(db: AsyncSession, account: Account, tour_id: int) -> RouteResponse:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to publish this tour")

    if not tour.draft_route:
        raise NotFoundException("No draft route found")

    if tour.price_usd is None:
        raise BadRequestException("Price must be set before publishing")

    # Get next version number
    result = await db.execute(
        select(func.max(Route.version)).where(Route.tour_id == tour_id)
    )
    max_version = result.scalar() or 0

    # Copy draft to new published route
    draft = tour.draft_route
    published = Route(
        tour_id=tour_id,
        version=max_version + 1,
        status="published",
        geojson=draft.geojson,
        waypoint_guids=draft.waypoint_guids,
        distance_m=draft.distance_m,
        elevation_m=draft.elevation_m,
        estimated_min=draft.estimated_min,
        languages=draft.languages,
    )
    db.add(published)
    await db.flush()

    # Update tour references
    tour.active_route_id = published.id

    # Clear coming_soon if first publish
    if tour.is_coming_soon:
        tour.is_coming_soon = False

    # Create new draft for future edits
    new_draft = Route(tour_id=tour_id, version=max_version + 2, status="draft")
    # Copy current state
    new_draft.geojson = published.geojson
    new_draft.waypoint_guids = published.waypoint_guids
    new_draft.distance_m = published.distance_m
    new_draft.elevation_m = published.elevation_m
    new_draft.estimated_min = published.estimated_min
    new_draft.languages = published.languages
    db.add(new_draft)
    await db.flush()

    tour.draft_route_id = new_draft.id
    await db.flush()

    return RouteResponse.model_validate(published)


async def get_route_history(
    db: AsyncSession, account: Account, tour_id: int
) -> list[RouteResponse]:
    tour = await get_tour_by_id(db, tour_id)
    if not tour:
        raise NotFoundException("Tour not found")
    if tour.created_by != account.id and account.role != "admin":
        raise ForbiddenException("Not authorized to access this tour")

    result = await db.execute(
        select(Route)
        .where(Route.tour_id == tour_id, Route.status == "published")
        .order_by(Route.version.desc())
    )
    routes = result.scalars().all()
    return [RouteResponse.model_validate(r) for r in routes]


# ============ Waypoints ============


async def create_waypoint(
    db: AsyncSession, account: Account, data: WaypointCreate
) -> WaypointResponse:
    from geoalchemy2.functions import ST_MakePoint

    waypoint = Waypoint(
        coordinates=func.ST_SetSRID(ST_MakePoint(data.lon, data.lat), 4326),
        description_i18n=data.description_i18n,
        is_checkpoint=data.is_checkpoint,
        created_by=account.id,
    )
    db.add(waypoint)
    await db.flush()

    return WaypointResponse(
        guid=waypoint.guid,
        lat=data.lat,
        lon=data.lon,
        description_i18n=waypoint.description_i18n,
        is_checkpoint=waypoint.is_checkpoint,
        created_at=waypoint.created_at,
    )


async def get_waypoint(db: AsyncSession, guid: UUID) -> WaypointResponse | None:
    result = await db.execute(select(Waypoint).where(Waypoint.guid == guid))
    waypoint = result.scalar_one_or_none()
    if not waypoint:
        return None

    lat = await db.scalar(func.ST_Y(waypoint.coordinates))
    lon = await db.scalar(func.ST_X(waypoint.coordinates))

    return WaypointResponse(
        guid=waypoint.guid,
        lat=lat,
        lon=lon,
        description_i18n=waypoint.description_i18n,
        is_checkpoint=waypoint.is_checkpoint,
        created_at=waypoint.created_at,
    )


async def update_waypoint(
    db: AsyncSession, account: Account, guid: UUID, data: WaypointUpdate
) -> WaypointResponse:
    result = await db.execute(select(Waypoint).where(Waypoint.guid == guid))
    waypoint = result.scalar_one_or_none()
    if not waypoint:
        raise NotFoundException("Waypoint not found")

    if data.description_i18n is not None:
        waypoint.description_i18n = data.description_i18n

    await db.flush()

    lat = await db.scalar(func.ST_Y(waypoint.coordinates))
    lon = await db.scalar(func.ST_X(waypoint.coordinates))

    return WaypointResponse(
        guid=waypoint.guid,
        lat=lat,
        lon=lon,
        description_i18n=waypoint.description_i18n,
        is_checkpoint=waypoint.is_checkpoint,
        created_at=waypoint.created_at,
    )


async def delete_waypoint(db: AsyncSession, guid: UUID) -> None:
    result = await db.execute(select(Waypoint).where(Waypoint.guid == guid))
    waypoint = result.scalar_one_or_none()
    if not waypoint:
        raise NotFoundException("Waypoint not found")

    # Check if waypoint is in use
    result = await db.execute(
        select(Route).where(Route.waypoint_guids.contains([guid]))
    )
    if result.scalar_one_or_none():
        raise ConflictException("Waypoint is in use by a route")

    await db.delete(waypoint)
    await db.flush()


# ============ Runs ============


async def get_runs(db: AsyncSession, account: Account, active_only: bool = False) -> list[RunResponse]:
    stmt = (
        select(Run)
        .options(selectinload(Run.route).selectinload(Route.tour))
        .where(Run.account_id == account.id)
    )

    if active_only:
        stmt = stmt.where(Run.completed_at.is_(None), Run.abandoned_at.is_(None))

    result = await db.execute(stmt.order_by(Run.started_at.desc()))
    runs = result.scalars().all()

    return [await _build_run_response(db, run) for run in runs]


async def create_run(db: AsyncSession, account: Account, data: RunCreate) -> RunResponse:
    # Get tour and verify entitlement
    result = await db.execute(
        select(Tour).options(selectinload(Tour.active_route)).where(Tour.id == data.tour_id)
    )
    tour = result.scalar_one_or_none()
    if not tour:
        raise NotFoundException("Tour not found")
    if not tour.active_route:
        raise BadRequestException("Tour has no active route")

    # Check entitlement (unless simulation)
    if not data.is_simulation:
        result = await db.execute(
            select(Entitlement).where(
                Entitlement.account_id == account.id, Entitlement.tour_id == data.tour_id
            )
        )
        if not result.scalar_one_or_none():
            raise ForbiddenException("Not entitled to this tour")

    # Check for existing active run
    result = await db.execute(
        select(Run).where(
            Run.account_id == account.id,
            Run.route_id == tour.active_route.id,
            Run.completed_at.is_(None),
            Run.abandoned_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException("Already have an active run for this tour")

    run = Run(
        route_id=tour.active_route.id,
        account_id=account.id,
        is_simulation=data.is_simulation,
        completed_checkpoints=[],
    )
    db.add(run)
    await db.flush()
    await db.refresh(run, ["route"])

    return await _build_run_response(db, run)


async def get_run(db: AsyncSession, account: Account, guid: UUID) -> RunResponse:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.route).selectinload(Route.tour))
        .where(Run.guid == guid, Run.account_id == account.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundException("Run not found")

    return await _build_run_response(db, run)


async def update_run(
    db: AsyncSession, account: Account, guid: UUID, data: RunUpdate
) -> RunResponse:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.route))
        .where(Run.guid == guid, Run.account_id == account.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundException("Run not found")

    if run.completed_at or run.abandoned_at:
        raise BadRequestException("Cannot update completed or abandoned run")

    # Set-union merge for completed_checkpoints
    if data.completed_checkpoints:
        existing = set(run.completed_checkpoints or [])
        new = set(data.completed_checkpoints)
        run.completed_checkpoints = list(existing | new)

    if data.last_position_lat is not None and data.last_position_lon is not None:
        run.last_position = func.ST_SetSRID(
            func.ST_MakePoint(data.last_position_lon, data.last_position_lat), 4326
        )

    await db.flush()
    return await _build_run_response(db, run)


async def abandon_run(db: AsyncSession, account: Account, guid: UUID) -> RunResponse:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.route))
        .where(Run.guid == guid, Run.account_id == account.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundException("Run not found")

    if run.completed_at:
        raise BadRequestException("Run already completed")
    if run.abandoned_at:
        raise BadRequestException("Run already abandoned")

    run.abandoned_at = datetime.now(timezone.utc)
    await db.flush()
    return await _build_run_response(db, run)


async def complete_run(db: AsyncSession, account: Account, guid: UUID) -> RunResponse:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.route))
        .where(Run.guid == guid, Run.account_id == account.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundException("Run not found")

    if run.completed_at:
        raise BadRequestException("Run already completed")
    if run.abandoned_at:
        raise BadRequestException("Run was abandoned")

    run.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return await _build_run_response(db, run)


async def _build_run_response(db: AsyncSession, run: Run) -> RunResponse:
    lat = None
    lon = None
    if run.last_position:
        lat = await db.scalar(func.ST_Y(run.last_position))
        lon = await db.scalar(func.ST_X(run.last_position))

    return RunResponse(
        guid=run.guid,
        route_id=run.route_id,
        tour_id=run.route.tour_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        abandoned_at=run.abandoned_at,
        completed_checkpoints=run.completed_checkpoints,
        is_simulation=run.is_simulation,
        last_position_lat=lat,
        last_position_lon=lon,
        updated_at=run.updated_at,
    )


# ============ User Lists ============


async def get_await_list(db: AsyncSession, account: Account) -> AwaitListResponse:
    result = await db.execute(
        select(AwaitList)
        .where(AwaitList.account_id == account.id)
        .order_by(AwaitList.created_at.desc())
    )
    items = result.scalars().all()
    return AwaitListResponse(
        count=len(items),
        items=[AwaitListItemResponse(tour_id=i.tour_id, created_at=i.created_at) for i in items],
    )


async def add_to_await_list(db: AsyncSession, account: Account, tour_id: int) -> None:
    # Verify tour exists and is coming soon
    result = await db.execute(
        select(Tour).where(Tour.id == tour_id, Tour.is_coming_soon == True)  # noqa: E712
    )
    if not result.scalar_one_or_none():
        raise BadRequestException("Tour not found or not coming soon")

    # Check existing
    result = await db.execute(
        select(AwaitList).where(
            AwaitList.account_id == account.id, AwaitList.tour_id == tour_id
        )
    )
    if result.scalar_one_or_none():
        return  # Idempotent

    item = AwaitList(account_id=account.id, tour_id=tour_id)
    db.add(item)
    await db.flush()


async def remove_from_await_list(db: AsyncSession, account: Account, tour_id: int) -> None:
    result = await db.execute(
        select(AwaitList).where(
            AwaitList.account_id == account.id, AwaitList.tour_id == tour_id
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.flush()


async def get_watch_list(db: AsyncSession, account: Account) -> WatchListResponse:
    result = await db.execute(
        select(WatchList)
        .where(WatchList.account_id == account.id)
        .order_by(WatchList.created_at.desc())
    )
    items = result.scalars().all()
    return WatchListResponse(
        count=len(items),
        items=[WatchListItemResponse(city_id=i.city_id, created_at=i.created_at) for i in items],
    )


async def add_to_watch_list(db: AsyncSession, account: Account, city_id: int) -> None:
    # Verify city exists
    result = await db.execute(select(City).where(City.geonameid == city_id))
    if not result.scalar_one_or_none():
        raise NotFoundException("City not found")

    # Check existing
    result = await db.execute(
        select(WatchList).where(
            WatchList.account_id == account.id, WatchList.city_id == city_id
        )
    )
    if result.scalar_one_or_none():
        return  # Idempotent

    item = WatchList(account_id=account.id, city_id=city_id)
    db.add(item)
    await db.flush()


async def remove_from_watch_list(db: AsyncSession, account: Account, city_id: int) -> None:
    result = await db.execute(
        select(WatchList).where(
            WatchList.account_id == account.id, WatchList.city_id == city_id
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.flush()


async def get_entitlements(db: AsyncSession, account: Account) -> EntitlementsResponse:
    result = await db.execute(
        select(Entitlement)
        .where(Entitlement.account_id == account.id)
        .order_by(Entitlement.created_at.desc())
    )
    items = result.scalars().all()
    return EntitlementsResponse(
        count=len(items),
        entitlements=[EntitlementResponse.model_validate(i) for i in items],
    )


# ============ Bundles ============


async def get_bundles(
    db: AsyncSession, account: Account | None = None, include_hidden: bool = False
) -> list[BundleResponse]:
    stmt = (
        select(Bundle)
        .options(selectinload(Bundle.tour_associations).selectinload(BundleToTour.tour))
        .where(Bundle.is_deleted == False)  # noqa: E712
    )

    result = await db.execute(stmt.order_by(Bundle.created_at.desc()))
    bundles = result.scalars().all()

    responses = []
    for bundle in bundles:
        # Calculate if should be hidden
        if account and not include_hidden:
            # Hide if user owns ANY tour in bundle
            result = await db.execute(
                select(Entitlement).where(
                    Entitlement.account_id == account.id,
                    Entitlement.tour_id.in_([ba.tour_id for ba in bundle.tour_associations]),
                )
            )
            if result.scalar_one_or_none():
                continue

        responses.append(_build_bundle_response(bundle))

    return responses


async def get_bundle_by_id(db: AsyncSession, bundle_id: int) -> BundleResponse | None:
    result = await db.execute(
        select(Bundle)
        .options(selectinload(Bundle.tour_associations).selectinload(BundleToTour.tour))
        .where(Bundle.id == bundle_id, Bundle.is_deleted == False)  # noqa: E712
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        return None
    return _build_bundle_response(bundle)


def _build_bundle_response(bundle: Bundle) -> BundleResponse:
    tours = []
    total_price = 0.0
    for ba in sorted(bundle.tour_associations, key=lambda x: x.display_order):
        tour = ba.tour
        price = float(tour.price_usd) if tour.price_usd else 0.0
        total_price += price
        tours.append(
            BundleTourResponse(
                tour_id=tour.id,
                display_order=ba.display_order,
                title_i18n=tour.title_i18n or {},
                price_usd=price,
            )
        )

    discount = None
    if total_price > 0:
        discount = round((1 - float(bundle.price_usd) / total_price) * 100, 1)

    return BundleResponse(
        id=bundle.id,
        title_i18n=bundle.title_i18n or {},
        description_i18n=bundle.description_i18n,
        price_usd=float(bundle.price_usd),
        discount_percent=discount if discount and discount > 0 else None,
        is_deleted=bundle.is_deleted,
        tours=tours,
        created_at=bundle.created_at,
    )


# ============ Admin ============


async def list_editors(db: AsyncSession) -> list[Account]:
    result = await db.execute(
        select(Account)
        .where(Account.role == "editor")
        .order_by(Account.created_at.desc())
    )
    return result.scalars().all()


async def grant_editor_role(db: AsyncSession, account_id: int) -> None:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundException("Account not found")

    if account.role == "admin":
        raise BadRequestException("Cannot change admin role")

    account.role = "editor"
    await db.flush()


async def revoke_editor_role(db: AsyncSession, account_id: int) -> None:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundException("Account not found")

    if account.role == "admin":
        raise BadRequestException("Cannot change admin role")

    account.role = "user"
    await db.flush()


async def create_bundle(db: AsyncSession, data: BundleCreate) -> BundleResponse:
    # Verify all tours exist and have prices
    result = await db.execute(select(Tour).where(Tour.id.in_(data.tour_ids)))
    tours = result.scalars().all()

    if len(tours) != len(data.tour_ids):
        raise BadRequestException("One or more tours not found")

    for tour in tours:
        if tour.price_usd is None:
            raise BadRequestException(f"Tour {tour.id} has no price set")

    bundle = Bundle(
        title_i18n=data.title_i18n,
        description_i18n=data.description_i18n,
        price_usd=data.price_usd,
    )
    db.add(bundle)
    await db.flush()

    for order, tour_id in enumerate(data.tour_ids):
        assoc = BundleToTour(bundle_id=bundle.id, tour_id=tour_id, display_order=order)
        db.add(assoc)

    await db.flush()
    await db.refresh(bundle, ["tour_associations"])

    # Load tours for response
    for assoc in bundle.tour_associations:
        await db.refresh(assoc, ["tour"])

    return _build_bundle_response(bundle)


async def delete_bundle(db: AsyncSession, bundle_id: int) -> None:
    result = await db.execute(select(Bundle).where(Bundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise NotFoundException("Bundle not found")

    bundle.is_deleted = True
    await db.flush()


async def get_all_bundles_admin(db: AsyncSession) -> list[BundleResponse]:
    result = await db.execute(
        select(Bundle)
        .options(selectinload(Bundle.tour_associations).selectinload(BundleToTour.tour))
        .order_by(Bundle.created_at.desc())
    )
    bundles = result.scalars().all()
    return [_build_bundle_response(b) for b in bundles]
