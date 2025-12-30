"""API endpoints for purchases module (US-013b)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.dependencies import CurrentUser
from app.database import get_db
from app.purchases import service
from app.purchases.schemas import (
    PurchaseVerifyRequest,
    PurchaseResponse,
    PurchaseListResponse,
    TripAccessResponse,
    TripAccessCheckRequest,
    TripAccessBatchResponse,
)
from app.routes.models import Route
from fastapi import Depends
from typing import Annotated

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/verify",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def verify_purchase(
    request: PurchaseVerifyRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Verify and record a purchase from Apple/Google store.

    - Validates receipt with the respective store
    - Creates purchase record if valid
    - Returns purchase details

    Note: Actual receipt validation with Apple/Google servers
    should be implemented in service layer.
    """
    # Check if trip exists
    result = await db.execute(select(Route).where(Route.id == request.route_id))
    trip = result.scalar_one_or_none()

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        )

    # Check if already purchased
    existing = await service.get_user_purchase(db, current_user.id, request.route_id)
    if existing:
        return PurchaseResponse.model_validate(existing)

    # TODO: Implement actual receipt validation with Apple/Google servers
    # For now, we create the purchase record directly
    # In production, this should:
    # 1. Call Apple/Google API to validate receipt
    # 2. Extract transaction ID and amount from validated receipt
    # 3. Create purchase record only if validation succeeds

    # Get price from published version
    if trip.published_version:
        amount = trip.published_version.price_amount or 0
        currency = trip.published_version.price_currency or "USD"
    else:
        amount = 0
        currency = "USD"

    purchase = await service.create_purchase(
        db=db,
        user_id=current_user.id,
        route_id=request.route_id,
        store_type=request.store_type,
        store_transaction_id=None,  # Would come from receipt validation
        amount=amount,
        currency=currency,
    )

    return PurchaseResponse.model_validate(purchase)


@router.get(
    "/me",
    response_model=PurchaseListResponse,
)
async def get_my_purchases(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get all purchases for current user."""
    purchases = await service.get_user_purchases(db, current_user.id)
    return PurchaseListResponse(
        purchases=[PurchaseResponse.model_validate(p) for p in purchases],
        count=len(purchases),
    )


@router.get(
    "/routes/{route_id}/access",
    response_model=TripAccessResponse,
)
async def check_trip_access(
    route_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Check user's access level to a trip.

    Returns access information including:
    - Whether user has full access
    - Reason for access (purchased, editor, free_preview, none)
    - Number of free checkpoints if in free preview mode
    """
    access = await service.check_trip_access(db, current_user, route_id)
    return access


@router.post(
    "/routes/access/batch",
    response_model=TripAccessBatchResponse,
)
async def check_trips_access_batch(
    request: TripAccessCheckRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Check access for multiple trips at once.

    Useful for trip listing pages where access status
    needs to be shown for multiple trips.
    """
    access = await service.check_trips_access_batch(
        db, current_user, request.route_ids
    )
    return TripAccessBatchResponse(access=access)
