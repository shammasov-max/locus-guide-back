"""Pydantic schemas for purchases module (US-013b)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PurchaseVerifyRequest(BaseModel):
    """Request to verify and record a purchase from app store."""

    route_id: UUID
    store_type: Literal["apple", "google"]
    receipt_data: str = Field(..., description="Base64 encoded receipt from store")


class PurchaseResponse(BaseModel):
    """Response with purchase details."""

    id: UUID
    route_id: UUID
    store_type: str
    amount: Decimal
    currency: str
    purchased_at: datetime

    model_config = {"from_attributes": True}


class PurchaseListResponse(BaseModel):
    """List of user's purchases."""

    purchases: list[PurchaseResponse]
    count: int


class TripAccessResponse(BaseModel):
    """Response indicating user's access level to a trip."""

    route_id: UUID
    has_full_access: bool
    access_reason: Literal["purchased", "editor", "free_preview", "none"]
    free_checkpoints_limit: int | None = None


class TripAccessCheckRequest(BaseModel):
    """Request to check access for multiple trips."""

    route_ids: list[UUID]


class TripAccessBatchResponse(BaseModel):
    """Batch response for trip access check."""

    access: dict[str, TripAccessResponse]  # route_id -> access info
