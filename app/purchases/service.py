"""Business logic for purchases module (US-013b, US-034)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AppUser
from app.purchases.models import UserPurchase
from app.purchases.schemas import TripAccessResponse
from app.routes.models import Route, RouteVersion


async def get_user_purchase(
    db: AsyncSession, user_id: int, route_id: UUID
) -> UserPurchase | None:
    """Get user's purchase for a specific trip."""
    result = await db.execute(
        select(UserPurchase).where(
            UserPurchase.user_id == user_id,
            UserPurchase.route_id == route_id,
        )
    )
    return result.scalar_one_or_none()


async def get_user_purchases(db: AsyncSession, user_id: int) -> list[UserPurchase]:
    """Get all purchases for a user."""
    result = await db.execute(
        select(UserPurchase)
        .where(UserPurchase.user_id == user_id)
        .order_by(UserPurchase.purchased_at.desc())
    )
    return list(result.scalars().all())


async def create_purchase(
    db: AsyncSession,
    user_id: int,
    route_id: UUID,
    store_type: str,
    store_transaction_id: str | None,
    amount: Decimal,
    currency: str,
) -> UserPurchase:
    """Create a new purchase record."""
    purchase = UserPurchase(
        user_id=user_id,
        route_id=route_id,
        store_type=store_type,
        store_transaction_id=store_transaction_id,
        amount=amount,
        currency=currency,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def check_trip_access(
    db: AsyncSession, user: AppUser, route_id: UUID
) -> TripAccessResponse:
    """Check user's access level to a trip (US-034).

    Access rules:
    1. Editor who created the trip has free full access
    2. User who purchased the trip has full access
    3. Otherwise, only free preview checkpoints are accessible
    """
    # Get trip with published version
    result = await db.execute(
        select(Route, RouteVersion)
        .outerjoin(RouteVersion, Route.published_version_id == RouteVersion.id)
        .where(Route.id == route_id)
    )
    row = result.one_or_none()

    if not row:
        return TripAccessResponse(
            route_id=route_id,
            has_full_access=False,
            access_reason="none",
            free_checkpoints_limit=0,
        )

    trip, version = row

    # US-034: Editor free access to their own trips
    if trip.created_by_user_id == user.id:
        return TripAccessResponse(
            route_id=route_id,
            has_full_access=True,
            access_reason="editor",
        )

    # Check for purchase
    purchase = await get_user_purchase(db, user.id, route_id)
    if purchase:
        return TripAccessResponse(
            route_id=route_id,
            has_full_access=True,
            access_reason="purchased",
        )

    # Free preview only
    free_limit = version.free_checkpoint_limit if version else 0
    return TripAccessResponse(
        route_id=route_id,
        has_full_access=False,
        access_reason="free_preview",
        free_checkpoints_limit=free_limit,
    )


async def check_trips_access_batch(
    db: AsyncSession, user: AppUser, route_ids: list[UUID]
) -> dict[str, TripAccessResponse]:
    """Check access for multiple trips at once."""
    result = {}
    for route_id in route_ids:
        access = await check_trip_access(db, user, route_id)
        result[str(route_id)] = access
    return result
