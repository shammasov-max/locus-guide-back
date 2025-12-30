"""SQLAlchemy models for user purchases (US-013b)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserPurchase(Base):
    """User's purchase of a trip.

    Tracks in-app purchases from Apple/Google stores.
    Used for:
    - Granting full access to trip content
    - Receipt validation
    - Purchase history
    """

    __tablename__ = "user_purchases"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_transaction_id: Mapped[str | None] = mapped_column(Text)
    store_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'apple', 'google'
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    route: Mapped["Route"] = relationship()  # type: ignore

    __table_args__ = (
        UniqueConstraint("user_id", "route_id", name="uq_user_purchase"),
        Index("idx_purchases_user", "user_id"),
        Index("idx_purchases_route", "route_id"),
    )
